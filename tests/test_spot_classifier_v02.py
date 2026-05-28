import copy
import json
from pathlib import Path

from solver_preflop.clear_json_adapter import parse_clear_json_preflop
from solver_preflop.spot_classifier import classify_preflop_spot
from solver_preflop import solve_clear_json


def _base():
    path = Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_bb_option_vs_two_limpers():
    data = _base()
    data["players"]["UTG"]["fold"] = False
    data["players"]["UTG"]["chips"] = 1.0

    frame = parse_clear_json_preflop(data)
    spot = classify_preflop_spot(frame)

    assert spot.node_type == "bb_option_vs_2plus_limpers"
    assert spot.to_call_bb == 0.0
    assert spot.limpers == ["UTG", "MP"]


def test_btn_iso_vs_one_limper():
    data = _base()

    # Move hero to BTN with no committed chips.
    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    data["players"]["BTN"]["hero"] = True
    data["players"]["BTN"]["cards"] = ["A_spades", "Q_hearts"]
    data["players"]["BTN"]["fold"] = False
    data["players"]["BTN"]["chips"] = False

    frame = parse_clear_json_preflop(data)
    spot = classify_preflop_spot(frame)

    assert frame.hero_position == "BTN"
    assert spot.node_type == "iso_vs_1_limper"
    assert spot.to_call_bb == 1.0


def test_unopened_btn_placeholder_open_raise():
    data = _base()

    # Move hero to BTN, remove limpers/openers.
    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    data["players"]["MP"]["fold"] = True
    data["players"]["MP"]["chips"] = False

    data["players"]["BTN"]["hero"] = True
    data["players"]["BTN"]["cards"] = ["A_spades", "Q_hearts"]
    data["players"]["BTN"]["fold"] = False
    data["players"]["BTN"]["chips"] = False

    decision = solve_clear_json(data)

    assert decision.node_type == "unopened"
    assert decision.raw_action == "open_raise"
    assert decision.click_sequence == ["Raise"]
