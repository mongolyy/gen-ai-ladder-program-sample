#!/usr/bin/env python3
"""
工程⑦ GX Works3 連携 — 中間成果物を GX Works3 取り込み用ファイルへ変換する。

入力:
  --devices  デバイスマスタ (label,device,type,io,comment)
  --st       ST ソース (任意。あれば取り込み用にそのままコピー出力)
出力:
  --labels   グローバルラベル CSV (GX Works3 のラベルエディタへ取り込む)
  --comments デバイスコメント CSV (任意。GX Works3 のデバイスコメントへ取り込む)
  --out-st   取り込み用 ST のコピー先 (任意)

注意:
  GX Works3 のラベル CSV の項目名・並びはバージョンや言語設定で異なる。
  本ツールは代表的な日本語版の並びで出力する。取り込み時にエラーが出る場合は
  references/gxworks3-export.md の手順に従い、実機の「ラベル一括取り込み」の
  テンプレート CSV に列を合わせること。
"""
import argparse
import csv
import io

# デバイスマスタの type → GX Works3 データ型表記
TYPE_MAP = {
    "BOOL": "ビット",
    "BIT": "ビット",
    "INT": "ワード[符号付き]",
    "WORD": "ワード[符号なし]/16ビット列",
    "DINT": "ダブルワード[符号付き]",
    "DWORD": "ダブルワード[符号なし]/32ビット列",
    "REAL": "単精度実数",
    "LREAL": "倍精度実数",
    "TIME": "時間",
    "STRING": "文字列(32)",
}

# グローバルラベル CSV の列 (代表的な日本語版 GX Works3)
LABEL_HEADER = ["ラベル名", "データ型", "クラス", "割付(デバイス/ラベル)", "コメント"]


def load_devices(path):
    rows = []
    # utf-8-sig: Excel 等が付与する BOM を除去 (BOM が残ると先頭列名が壊れ全行スキップになる)
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            # ヘッダより多い列は DictReader が key=None / value=list を返すため除外・ガード
            clean = {k: v.strip() if isinstance(v, str) else ""
                     for k, v in row.items() if k is not None}
            if not clean.get("label"):
                continue
            rows.append(clean)
    return rows


def map_type(raw):
    return TYPE_MAP.get((raw or "").upper(), raw or "")


def write_global_labels(devices, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(LABEL_HEADER)
        for d in devices:
            w.writerow([
                d.get("label", ""),
                map_type(d.get("type", "")),
                "VAR_GLOBAL",
                d.get("device", ""),
                d.get("comment", ""),
            ])
    return len(devices)


def _read_template(path):
    """GX Works3 がエクスポートしたラベル CSV テンプレートを解析する。
    バージョン/言語で列・区切り・エンコードが異なるため、実物から読み取る。
    戻り値: (preamble_lines, header_list, delimiter, newline, encoding)
    """
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        encoding = "utf-16"            # BOM 付き。codecs が LE/BE を判別
    elif raw[:3] == b"\xef\xbb\xbf":
        encoding = "utf-8-sig"
    else:
        encoding = "utf-8"
    text = raw.decode(encoding)
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    # ヘッダ行 = 列数が最大（タブ/カンマが最も多い）の行。手前はプリアンブル（プロジェクト名等）
    delimiter = "\t" if "\t" in text else ","
    hdr_idx = max(range(len(lines)),
                  key=lambda i: lines[i].count(delimiter))
    header = next(csv.reader(io.StringIO(lines[hdr_idx]), delimiter=delimiter))
    preamble = lines[:hdr_idx]
    # エクスポート元は UTF-16 でも BOM 付きで書き戻したいので LE を明示
    out_enc = "utf-16-le" if encoding == "utf-16" else encoding
    return preamble, header, delimiter, newline, out_enc


def _value_for_column(col, dev):
    """テンプレートのヘッダ名から、その列に入れる値を決める（バージョン差異に頑健）。"""
    c = col.replace("　", "").strip()
    if c == "クラス":
        return "VAR_GLOBAL"
    if c == "ラベル名":
        return dev.get("label", "")
    if c == "データ型":
        return map_type(dev.get("type", ""))
    if "割付" in c:                              # 割付け(デバイス/ラベル)
        return dev.get("device", "")
    if c == "コメント" or "Japanese" in c or "日本語" in c:
        return dev.get("comment", "")
    return ""                                    # 定数/初期値/他言語/予約列など


def write_global_labels_from_template(devices, path, template):
    """実機エクスポートのテンプレートに列・区切り・エンコードを完全一致させて出力。"""
    preamble, header, delimiter, newline, out_enc = _read_template(template)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delimiter, quoting=csv.QUOTE_ALL,
                   lineterminator=newline)
    for line in preamble:                        # プロジェクト名行などをそのまま再現
        buf.write(line + newline)
    w.writerow(header)
    for d in devices:
        w.writerow([_value_for_column(col, d) for col in header])
    data = buf.getvalue()
    with open(path, "wb") as f:
        if out_enc == "utf-16-le":
            f.write(b"\xff\xfe")                 # UTF-16 LE BOM
        elif out_enc == "utf-8-sig":
            f.write(b"\xef\xbb\xbf")
            out_enc = "utf-8"
        f.write(data.encode("utf-16-le" if out_enc == "utf-16-le" else out_enc))
    return len(devices)


def write_device_comments(devices, path):
    n = 0
    seen = set()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["デバイス", "コメント"])
        for d in devices:
            dev = d.get("device", "")
            comment = d.get("comment", "")
            # 空コメントは既存コメントの上書き事故を避けて出力しない。デバイス重複も排除。
            if not dev or not comment or dev in seen:
                continue
            seen.add(dev)
            w.writerow([dev, comment])
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description="工程⑦ GX Works3 取り込み用ファイル生成")
    ap.add_argument("--devices", required=True, help="デバイスマスタ CSV")
    ap.add_argument("--st", help="ST ソース (取り込み用コピー元)")
    ap.add_argument("--labels", required=True, help="グローバルラベル CSV 出力先")
    ap.add_argument("--label-template", dest="label_template",
                    help="GX Works3 からエクスポートしたラベル CSV。指定すると "
                         "その列・区切り・エンコードに完全一致させて出力する "
                         "(バージョン差異によるインポート失敗の確実な対処)")
    ap.add_argument("--comments", help="デバイスコメント CSV 出力先 (任意)")
    ap.add_argument("--out-st", dest="out_st", help="ST コピー出力先 (任意)")
    args = ap.parse_args()

    devices = load_devices(args.devices)
    if args.label_template:
        n_lbl = write_global_labels_from_template(
            devices, args.labels, args.label_template)
        print(f"[OK] グローバルラベル CSV (テンプレート整合): "
              f"{args.labels} ({n_lbl} 件)")
    else:
        n_lbl = write_global_labels(devices, args.labels)
        print(f"[OK] グローバルラベル CSV: {args.labels} ({n_lbl} 件)")

    # 割付未確定 (device 空) の警告
    missing = [d["label"] for d in devices if not d.get("device")]
    if missing:
        print(f"[WARN] デバイス割付が未確定のラベル {len(missing)} 件: "
              f"{', '.join(missing[:10])}{' …' if len(missing) > 10 else ''}")
        print("       工程③ デバイス/ラベル割付を確定してから取り込むこと。")

    if args.comments:
        n_cmt = write_device_comments(devices, args.comments)
        print(f"[OK] デバイスコメント CSV: {args.comments} ({n_cmt} 件)")

    if args.out_st:
        if not args.st:
            print("[WARN] --out-st 指定だが --st が無いため ST はコピーしない")
        else:
            with open(args.st, encoding="utf-8") as src, \
                    open(args.out_st, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            print(f"[OK] 取り込み用 ST: {args.out_st}")

    print("\n次の手順は references/gxworks3-export.md を参照。")


if __name__ == "__main__":
    main()
