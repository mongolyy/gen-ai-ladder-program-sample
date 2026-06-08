"""export_gxworks3.py の入出力の堅牢性テスト。"""
import csv

import export_gxworks3 as gx


def write(path, content, encoding="utf-8"):
    path.write_text(content, encoding=encoding)
    return str(path)


def test_load_devices_handles_bom(tmp_path):
    # Excel 等が付ける BOM があっても先頭列名 label が壊れず読めること
    p = write(tmp_path / "d.csv",
              "label,device,type,io,comment\nA,Y0,BOOL,output,ランプ\n",
              encoding="utf-8-sig")
    rows = gx.load_devices(p)
    assert len(rows) == 1
    assert rows[0]["label"] == "A"
    assert rows[0]["device"] == "Y0"


def test_load_devices_guards_extra_columns(tmp_path):
    # ヘッダより多い列 (末尾カンマ等) があっても AttributeError でクラッシュしない
    p = write(tmp_path / "d.csv",
              "label,device,type,io,comment\nA,Y0,BOOL,output,c,EXTRA\n")
    rows = gx.load_devices(p)
    assert len(rows) == 1
    assert rows[0]["label"] == "A"


def test_load_devices_skips_rows_without_label(tmp_path):
    p = write(tmp_path / "d.csv",
              "label,device,type,io,comment\n,Y0,BOOL,output,c\nB,Y1,BOOL,output,d\n")
    rows = gx.load_devices(p)
    assert [r["label"] for r in rows] == ["B"]


def test_map_type():
    assert gx.map_type("BOOL") == "ビット"
    assert gx.map_type("int") == "ワード[符号付き]"
    assert gx.map_type("UNKNOWN_T") == "UNKNOWN_T"


def test_write_device_comments_dedups_and_skips_empty(tmp_path):
    devices = [
        {"device": "Y0", "comment": "ランプ"},
        {"device": "Y0", "comment": "別名"},   # 重複デバイス → 出力しない
        {"device": "Y1", "comment": ""},        # 空コメント → 出力しない
        {"device": "Y2", "comment": "弁"},
    ]
    out = tmp_path / "cmt.csv"
    n = gx.write_device_comments(devices, str(out))
    assert n == 2
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["デバイス", "コメント"]
    data = rows[1:]
    assert ["Y0", "ランプ"] in data
    assert ["Y2", "弁"] in data
    assert all(r[0] != "Y1" for r in data)


def test_write_global_labels(tmp_path):
    devices = [{"label": "A", "device": "Y0", "type": "BOOL", "comment": "x"}]
    out = tmp_path / "lbl.csv"
    gx.write_global_labels(devices, str(out))
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0][0] == "ラベル名"
    assert rows[1][:4] == ["A", "ビット", "VAR_GLOBAL", "Y0"]
