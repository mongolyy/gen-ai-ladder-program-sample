"""gen_state_machine.py の生成・検証テスト。"""
import pytest

import gen_state_machine as gsm


def test_build_state_machine_basic():
    spec = {
        "meta": {"name": "t"},
        "states": [{"id": "IDLE"}, {"id": "RUN"}],
        "transitions": [{"from": "IDLE", "to": "RUN", "condition": "START"}],
    }
    st = gsm.build_state_machine(spec, "STATE")
    assert "CASE STATE OF" in st
    assert "END_CASE;" in st
    assert "0: (* IDLE" in st
    assert "1: (* RUN" in st
    assert "IF START THEN" in st
    assert "STATE := 1;" in st
    # ELSE フェイルセーフで初期状態へ戻る
    assert "STATE := 0;" in st


def test_no_states_exits():
    with pytest.raises(SystemExit) as exc:
        gsm.build_state_machine({"states": []}, "STATE")
    assert exc.value.code != 0


def test_invalid_state_element_exits():
    with pytest.raises(SystemExit) as exc:
        gsm.build_state_machine({"states": ["IDLE"]}, "STATE")
    assert exc.value.code != 0


def test_unknown_transition_from_exits():
    spec = {
        "states": [{"id": "IDLE"}],
        "transitions": [{"from": "NOPE", "to": "IDLE"}],
    }
    with pytest.raises(SystemExit) as exc:
        gsm.build_state_machine(spec, "STATE")
    assert exc.value.code != 0


def test_unknown_transition_to_exits():
    spec = {
        "states": [{"id": "IDLE"}],
        "transitions": [{"from": "IDLE", "to": "NOPE"}],
    }
    with pytest.raises(SystemExit) as exc:
        gsm.build_state_machine(spec, "STATE")
    assert exc.value.code != 0


def test_load_spec_missing_file_exits():
    with pytest.raises(SystemExit) as exc:
        gsm.load_spec("/nonexistent/spec.yaml")
    assert exc.value.code != 0
