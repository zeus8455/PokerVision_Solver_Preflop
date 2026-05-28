import json
from pathlib import Path

import pytest

from solver_preflop.clear_json_adapter import parse_clear_json_preflop
from solver_preflop import solve_clear_json


def _base():
    path = Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_absent_all_in_is_false():
    data = _base()
    frame = parse_clear_json_preflop(data)
    assert frame.players["BB"].all_in is False
    assert frame.players["MP"].all_in is False


def test_all_in_true_requires_numeric_chips():
    data = _base()
    data["players"]["MP"]["all_in"] = True
    data["players"]["MP"]["chips"] = False

    with pytest.raises(ValueError, match="all_in=true requires numeric chips"):
        parse_clear_json_preflop(data)


def test_all_in_true_with_chips_is_valid_and_guarded_fallback_node():
    data = _base()
    data["players"]["MP"]["all_in"] = True
    data["players"]["MP"]["chips"] = 7.5

    decision = solve_clear_json(data)

    assert decision.status == "fallback"
    assert decision.node_type in {
        "facing_open_jam",
        "blind_vs_open_jam",
        "facing_allin_or_allin_present",
    }
    assert decision.click_sequence == ["Check", "Check/fold", "FOLD"]
    assert decision.debug["all_in_players"] == ["MP"]


def test_already_clicked_json_is_rejected_to_fallback():
    data = _base()
    data["click_result"] = {"status": "clicked"}

    decision = solve_clear_json(data)

    assert decision.status == "fallback"
    assert decision.node_type == "solver_input_error"
    assert decision.click_sequence == ["Check", "Check/fold", "FOLD"]
    assert "already has click_result" in decision.reason


def test_fold_false_and_chips_false_is_active_zero_bb():
    data = _base()
    data["players"]["UTG"]["fold"] = False
    data["players"]["UTG"]["chips"] = False

    frame = parse_clear_json_preflop(data)

    assert frame.players["UTG"].active_in_hand is True
    assert frame.players["UTG"].committed_bb == 0.0


def test_sitout_if_present_excludes_player():
    data = _base()
    data["players"]["UTG"]["sitout"] = True
    data["players"]["UTG"]["fold"] = False
    data["players"]["UTG"]["chips"] = False

    frame = parse_clear_json_preflop(data)

    assert frame.players["UTG"].sitout is True
    assert frame.players["UTG"].active_in_hand is False
