#!/usr/bin/env python3
"""
工程④補助 状態遷移 → CASE 状態機械の ST 生成。

構造化仕様 (states / transitions) を読み、状態変数を使った CASE 文の
ST スケルトンを生成する。シーケンス制御の骨格づくりに使う。

使い方:
  python3 gen_state_machine.py --spec spec.yaml [--state-var STATE] [--out sm.st]

生成物の前提:
  - 状態変数 (既定 STATE, INT) をデバイスマスタに追加すること。
  - 各状態の出力動作 (Moore 動作) はコメント枠を出力するので人間/AI が埋める。
"""
import argparse
import sys


def load_spec(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        import yaml
    except ImportError:
        sys.exit("ERROR: pyyaml が必要です (pip install pyyaml)。"
                 "状態機械生成は構造化された states/transitions の解釈に YAML を使います。")
    return yaml.safe_load(text)


def build_state_machine(spec, state_var):
    meta = spec.get("meta") or {}
    states = spec.get("states") or []
    transitions = spec.get("transitions") or []
    if not states:
        sys.exit("ERROR: spec に states がありません。状態機械を生成できません。")

    # 状態 id → 番号
    enc = {s["id"]: i for i, s in enumerate(states)}

    # 遷移を from 状態ごとにまとめる
    by_from = {}
    for t in transitions:
        frm = t.get("from")
        if frm not in enc:
            sys.exit(f"ERROR: transition の from '{frm}' が states に存在しません。")
        if t.get("to") not in enc:
            sys.exit(f"ERROR: transition の to '{t.get('to')}' が states に存在しません。")
        by_from.setdefault(frm, []).append(t)

    out = []
    out.append("(* ============================================================")
    out.append(f"   状態機械: {meta.get('name', '(no name)')}")
    out.append(f"   状態変数: {state_var} (INT)。デバイスマスタへ追加すること。")
    out.append("   状態エンコード:")
    for s in states:
        out.append(f"     {enc[s['id']]} = {s['id']}  {s.get('description', '')}")
    out.append("   自動生成（要レビュー）。各状態の出力動作は TODO を埋める。")
    out.append("   ============================================================ *)")
    out.append("")
    out.append(f"CASE {state_var} OF")
    for s in states:
        sid = s["id"]
        out.append(f"    {enc[sid]}: (* {sid}  {s.get('description', '')} *)")
        out.append(f"        (* TODO: {sid} での出力動作をここに記述 *)")
        outs = by_from.get(sid, [])
        if outs:
            for t in outs:
                cond = (t.get("condition") or "TRUE").strip()
                to = t["to"]
                out.append(f"        IF {cond} THEN")
                out.append(f"            {state_var} := {enc[to]}; (* -> {to} *)")
                out.append("        END_IF;")
        else:
            out.append(f"        (* {sid} からの遷移なし *)")
    out.append("    ELSE")
    out.append(f"        {state_var} := {enc[states[0]['id']]};"
               f" (* 不正状態は初期状態 {states[0]['id']} へ *)")
    out.append("END_CASE;")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="状態遷移 → CASE 状態機械 ST 生成")
    ap.add_argument("--spec", required=True, help="構造化仕様 YAML")
    ap.add_argument("--state-var", default="STATE", help="状態変数ラベル (既定 STATE)")
    ap.add_argument("--out", help="出力 ST ファイル (省略時は標準出力)")
    args = ap.parse_args()

    spec = load_spec(args.spec)
    st = build_state_machine(spec, args.state_var)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(st + "\n")
        print(f"[OK] 状態機械 ST を出力: {args.out}")
    else:
        print(st)


if __name__ == "__main__":
    main()
