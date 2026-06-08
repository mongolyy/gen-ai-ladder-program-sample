"""static_check.py の検査ルールの回帰テスト。"""
import static_check as sc


def devmap(*labels):
    return {lbl: {"label": lbl, "device": "", "type": "BOOL", "io": "internal"}
            for lbl in labels}


def findings(st_text, devices, spec=None):
    st = sc.analyze_st(st_text)
    return sc.run_checks(st, devices, spec)


def ids(found):
    return sorted(f[1] for f in found)


def errors(found):
    return [f for f in found if f[0] == "ERROR"]


def test_clean_program_has_no_errors():
    spec = {
        "safety": {"estop": {"label": "ESTOP"}},
        "io": {"outputs": [{"label": "MOTOR"}]},
        "interlocks": [],
    }
    found = findings("MOTOR := A AND ESTOP;", devmap("MOTOR", "A", "ESTOP"), spec)
    assert errors(found) == []


def test_double_coil_detected():
    found = findings("X := A;\nX := B;", devmap("X", "A", "B"))
    assert "C001" in ids(found)


def test_if_else_branches_are_not_double_coil():
    text = "IF A THEN\n X := TRUE;\nELSE\n X := FALSE;\nEND_IF;"
    found = findings(text, devmap("X", "A"))
    assert "C001" not in ids(found)


def test_case_branches_are_not_double_coil():
    text = "CASE S OF\n 1: X := TRUE;\n 2: X := FALSE;\nEND_CASE;"
    found = findings(text, devmap("X", "S"))
    assert "C001" not in ids(found)


def test_label_containing_keyword_substring_does_not_break_blocks():
    # DRIFT は "IF" を含む。単語境界が無いと block_stack が壊れ C001/C007 を誤検出する。
    text = "IF A THEN\n DRIFT := TRUE;\nELSE\n DRIFT := FALSE;\nEND_IF;"
    found = findings(text, devmap("DRIFT", "A"))
    assert "C001" not in ids(found)
    assert "C007" not in ids(found)


def test_timer_fb_inputs_are_not_treated_as_coils():
    # IN:= / PT:= は代入先(コイル)ではないため二重コイルにしない。
    text = "T_A(IN := A, PT := T#5s);\nT_B(IN := B, PT := T#3s);"
    found = findings(text, devmap("A", "B", "T_A", "T_B"))
    assert "C001" not in ids(found)


def test_undefined_device_detected():
    found = findings("X := UNDEF;", devmap("X"))
    assert "C002" in ids(found)


def test_missing_estop_detected():
    spec = {"safety": {"estop": {"label": "ESTOP"}}}
    found = findings("X := A;", devmap("X", "A", "ESTOP"), spec)
    assert "C003" in ids(found)


def test_interlock_not_implemented_detected():
    spec = {"interlocks": [{"name": "正逆同時禁止", "forbid": "MFWD AND MREV"}]}
    found = findings("X := A;", devmap("X", "A", "MFWD", "MREV"), spec)
    assert "C004" in ids(found)


def test_if_balance_counts_keywords_only_with_word_boundary():
    st = sc.analyze_st("DRIFT := A;")  # IF を含むが IF 文ではない
    assert st["if_balance"] == (0, 0)
