#!/usr/bin/env python3
"""
工程⑤ 静的チェッカー — 生成された ST(構造化テキスト) を検査する。

検査項目 (references/static-check-rules.md と一致):
  C001 ERROR 二重コイル        同一出力への代入が複数 (IF/ELSE の相互排他分岐は除外)
  C002 ERROR 未定義デバイス    ST 中のラベルがデバイスマスタに無い
  C003 ERROR 非常停止欠落      safety.estop.label が ST で参照されていない
  C004 ERROR インターロック    interlocks の forbid 対象ラベルが ST に出てこない
  C005 WARN  未使用デバイス    マスタにあるが ST で未使用
  C006 WARN  出力ロジック欠落  io.outputs のラベルが ST で代入されない
  C007 WARN  構文対応崩れ      IF/END_IF, CASE/END_CASE の数が不一致

使い方:
  python3 static_check.py --st prog.st --devices dev.csv [--spec spec.yaml] [--report out.txt]

終了コード: ERROR が 1 件以上なら 1、無ければ 0。
"""
import argparse
import csv
import re
import sys

# ----- ST キーワード/予約語 (ラベルではないもの) -----
ST_KEYWORDS = {
    "IF", "THEN", "ELSE", "ELSIF", "END_IF", "CASE", "OF", "END_CASE",
    "WHILE", "DO", "END_WHILE", "FOR", "TO", "BY", "END_FOR",
    "REPEAT", "UNTIL", "END_REPEAT", "RETURN", "EXIT", "CONTINUE",
    "AND", "OR", "NOT", "XOR", "MOD", "TRUE", "FALSE",
    "VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_GLOBAL", "END_VAR",
    "FUNCTION", "FUNCTION_BLOCK", "END_FUNCTION", "END_FUNCTION_BLOCK",
    "PROGRAM", "END_PROGRAM", "STRUCT", "END_STRUCT",
    # 型名
    "BOOL", "INT", "DINT", "UINT", "WORD", "DWORD", "REAL", "LREAL",
    "TIME", "STRING", "BYTE",
    # 代表的なタイマ/カウンタ FB と入出力端子
    "TON", "TOF", "TP", "CTU", "CTD", "CTUD",
    "IN", "PT", "ET", "Q", "CV", "CU", "CD", "PV", "R", "LD",
    # 代表的な命令/関数
    "SET", "RST", "MOV", "TON_MS", "ABS", "MIN", "MAX", "LIMIT", "SEL",
}

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ASSIGN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:=")


def strip_comments(text):
    """ST コメント (* ... *) と // 行コメントを除去。"""
    text = re.sub(r"\(\*.*?\*\)", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def strip_literals(text):
    """時間リテラル T#5s / TIME#... と文字列リテラルを除去。"""
    text = re.sub(r"\b[tT]#\S+", " ", text)
    text = re.sub(r"\bTIME#\S+", " ", text)
    text = re.sub(r"'[^']*'", " ", text)
    text = re.sub(r'"[^"]*"', " ", text)
    return text


def load_devices(path):
    """デバイスマスタ CSV を読む。{label: row} を返す。"""
    devices = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("label") or "").strip()
            if label:
                devices[label] = {k: (v or "").strip() for k, v in row.items()}
    return devices


def load_spec(path):
    """構造化仕様 YAML を読む。pyyaml が無ければ簡易フォールバック。"""
    if path is None:
        return None, None
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        import yaml
        return yaml.safe_load(text), None
    except ImportError:
        return _fallback_spec(text), (
            "pyyaml 未導入のため簡易解析を使用 (pip install pyyaml を推奨)"
        )


def _fallback_spec(text):
    """pyyaml 無し時の最小フォールバック。estop/outputs/interlocks のみ抽出。"""
    spec = {"io": {"outputs": []}, "safety": {"estop": {}}, "interlocks": []}
    # estop ラベル
    m = re.search(r"estop:\s*\n\s*label:\s*(\S+)", text)
    if m:
        spec["safety"]["estop"]["label"] = m.group(1).strip().strip('"')
    # outputs ラベル (outputs: ブロック内の label:)
    out_block = re.search(r"outputs:(.*?)(?:\n\w|\Z)", text, flags=re.DOTALL)
    if out_block:
        for lm in re.finditer(r"label:\s*(\S+)", out_block.group(1)):
            spec["io"]["outputs"].append({"label": lm.group(1).strip().strip('"')})
    # interlocks の forbid
    for fm in re.finditer(r"forbid:\s*(.+)", text):
        spec["interlocks"].append({"forbid": fm.group(1).strip().strip('"')})
    return spec


# ---------------- ST 解析 ----------------
def analyze_st(text):
    """ST を解析し、代入ターゲット・使用ラベル・ブロック整合を返す。"""
    clean = strip_literals(strip_comments(text))

    used = set(
        tok for tok in IDENT_RE.findall(clean)
        if tok.upper() not in ST_KEYWORDS and not tok[0].isdigit()
    )

    # 代入ターゲットをブロック文脈つきで収集 (二重コイル判定用)
    assigns = []  # list of (label, context) context = list[(block_id, branch_idx)]
    block_stack = []  # list of [block_id, branch_idx]
    next_block_id = [0]

    tokens = re.findall(r"END_IF|END_CASE|ELSIF|ELSE|IF|CASE|[A-Za-z_][A-Za-z0-9_]*\s*:=|.",
                        clean)
    for tok in tokens:
        t = tok.strip()
        up = t.upper()
        if up in ("IF", "CASE"):
            block_stack.append([next_block_id[0], 0])
            next_block_id[0] += 1
        elif up in ("ELSIF", "ELSE"):
            if block_stack:
                block_stack[-1][1] += 1
        elif up in ("END_IF", "END_CASE"):
            if block_stack:
                block_stack.pop()
        elif t.endswith(":="):
            label = t[:-2].strip()
            assigns.append((label, [tuple(b) for b in block_stack]))

    # 構文対応
    if_open = len(re.findall(r"\bIF\b", clean))
    if_close = len(re.findall(r"\bEND_IF\b", clean))
    case_open = len(re.findall(r"\bCASE\b", clean))
    case_close = len(re.findall(r"\bEND_CASE\b", clean))

    return {
        "used": used,
        "assigns": assigns,
        "assign_labels": set(a[0] for a in assigns),
        "if_balance": (if_open, if_close),
        "case_balance": (case_open, case_close),
    }


def mutually_exclusive(ctx_a, ctx_b):
    """2 つの代入が IF/CASE の相互排他分岐にあるか。"""
    for (bid_a, br_a) in ctx_a:
        for (bid_b, br_b) in ctx_b:
            if bid_a == bid_b and br_a != br_b:
                return True
    return False


def extract_labels(expr):
    """疑似ブール式から識別子を抽出 (キーワード除外)。"""
    return set(
        tok for tok in IDENT_RE.findall(expr or "")
        if tok.upper() not in ST_KEYWORDS and not tok[0].isdigit()
    )


# ---------------- チェック本体 ----------------
def run_checks(st, devices, spec):
    findings = []  # (severity, id, message)

    # C001 二重コイル
    by_label = {}
    for label, ctx in st["assigns"]:
        by_label.setdefault(label, []).append(ctx)
    for label, ctxs in by_label.items():
        if len(ctxs) <= 1:
            continue
        conflict = False
        for i in range(len(ctxs)):
            for j in range(i + 1, len(ctxs)):
                if not mutually_exclusive(ctxs[i], ctxs[j]):
                    conflict = True
        if conflict:
            findings.append(("ERROR", "C001",
                             f"二重コイル: '{label}' への代入が {len(ctxs)} 箇所 (相互排他でない)"))

    # C002 未定義デバイス
    known = set(devices.keys())
    for label in sorted(st["used"]):
        if label not in known:
            findings.append(("ERROR", "C002", f"未定義デバイス: '{label}' がマスタに無い"))

    # spec 依存チェック
    if spec:
        # C003 非常停止欠落
        estop = (((spec.get("safety") or {}).get("estop") or {}).get("label"))
        if estop and estop not in st["used"]:
            findings.append(("ERROR", "C003",
                             f"非常停止欠落: '{estop}' が ST で参照されていない"))

        # C004 インターロック未実装
        for il in (spec.get("interlocks") or []):
            forbid = il.get("forbid") if isinstance(il, dict) else None
            for lab in extract_labels(forbid):
                if lab not in st["used"]:
                    name = il.get("name", forbid) if isinstance(il, dict) else forbid
                    findings.append(("ERROR", "C004",
                                     f"インターロック未実装: '{name}' の '{lab}' が ST に無い"))

        # C006 出力ロジック欠落
        for out in ((spec.get("io") or {}).get("outputs") or []):
            lab = out.get("label") if isinstance(out, dict) else out
            if lab and lab not in st["assign_labels"]:
                findings.append(("WARN", "C006",
                                 f"出力ロジック欠落: 出力 '{lab}' が ST で代入されない"))

    # C005 未使用デバイス
    for label in sorted(known):
        if label not in st["used"]:
            findings.append(("WARN", "C005", f"未使用デバイス: '{label}' が ST で未使用"))

    # C007 構文対応崩れ
    if st["if_balance"][0] != st["if_balance"][1]:
        findings.append(("WARN", "C007",
                         f"IF/END_IF 不一致: IF={st['if_balance'][0]} END_IF={st['if_balance'][1]}"))
    if st["case_balance"][0] != st["case_balance"][1]:
        findings.append(("WARN", "C007",
                         f"CASE/END_CASE 不一致: CASE={st['case_balance'][0]} END_CASE={st['case_balance'][1]}"))

    return findings


def format_report(findings, notes):
    lines = ["=== 静的チェック結果 (工程⑤) ==="]
    for n in notes:
        lines.append(f"[NOTE] {n}")
    errors = [f for f in findings if f[0] == "ERROR"]
    warns = [f for f in findings if f[0] == "WARN"]
    if not findings:
        lines.append("問題は検出されませんでした。")
    for sev, cid, msg in findings:
        lines.append(f"[{sev}] {cid} {msg}")
    lines.append("")
    lines.append(f"ERROR: {len(errors)} 件 / WARN: {len(warns)} 件")
    if errors:
        lines.append(">>> ERROR が残っています。工程②/③/④へ戻して修正してください。")
    else:
        lines.append(">>> ERROR なし。工程⑥(人間レビュー)へ進めます。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="工程⑤ ST 静的チェッカー")
    ap.add_argument("--st", required=True, help="ST ソース (.st)")
    ap.add_argument("--devices", required=True, help="デバイスマスタ (.csv)")
    ap.add_argument("--spec", help="構造化仕様 (.yaml) 任意だが推奨")
    ap.add_argument("--report", help="レポート出力先 (省略時は標準出力のみ)")
    args = ap.parse_args()

    with open(args.st, encoding="utf-8") as f:
        st_text = f.read()
    devices = load_devices(args.devices)
    spec, note = load_spec(args.spec)
    notes = [note] if note else []
    if args.spec is None:
        notes.append("--spec 未指定: C003/C004/C006 (安全/インターロック/出力欠落) は未検査")

    st = analyze_st(st_text)
    findings = run_checks(st, devices, spec)
    report = format_report(findings, notes)

    print(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report + "\n")

    errors = sum(1 for s, _, _ in findings if s == "ERROR")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
