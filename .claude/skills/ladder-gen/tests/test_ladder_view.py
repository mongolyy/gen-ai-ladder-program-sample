"""ladder_view.py のパーサ・描画テスト。"""
import pytest

import ladder_view as lv


def test_extract_assignments():
    text = "(* c *)\nX := A AND B;\nY := C;\n"
    assert lv.extract_assignments(text) == [("X", "A AND B"), ("Y", "C")]


def test_extract_assignments_ignores_fb_param_nesting():
    # 左辺が単純識別子でない文 (FB 呼び出し) は対象外
    text = "T_A(IN := A, PT := T#5s);\nX := A;"
    assert lv.extract_assignments(text) == [("X", "A")]


def test_parse_and_or_not():
    node = lv.Parser(lv.tokenize_bool("A AND (B OR NOT C)")).parse()
    assert node[0] == "and"
    sub = node[1]
    assert sub[0] == ("var", "A", False)
    assert sub[1][0] == "or"


def test_not_distributes_over_parens_de_morgan():
    # NOT(A AND B) -> OR(NOT A, NOT B)
    node = lv.Parser(lv.tokenize_bool("NOT (A AND B)")).parse()
    assert node[0] == "or"
    negated = {(n[1], n[2]) for n in node[1]}
    assert negated == {("A", True), ("B", True)}


def test_unsupported_expression_raises():
    with pytest.raises(lv.ParseError):
        lv.tokenize_bool("SPEED >= 100")


def test_render_rung_has_rails_and_coil():
    node = lv.Parser(lv.tokenize_bool("A AND B")).parse()
    lines = lv.render_rung("OUT", node)
    assert all(ln.startswith("|") and ln.endswith("|") for ln in lines)
    assert any("( )" in ln for ln in lines)
    assert any("] [" in ln for ln in lines)


def test_render_negated_contact():
    node = lv.Parser(lv.tokenize_bool("NOT A")).parse()
    lines = lv.render_rung("OUT", node)
    assert any("]/[" in ln for ln in lines)
