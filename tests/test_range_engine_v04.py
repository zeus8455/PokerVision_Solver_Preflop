import json
from pathlib import Path

from solver_preflop import solve_clear_json


def _base():
    path = Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _move_hero(data, pos, cards=("A_spades", "Q_hearts"), chips=False):
    for player in data["players"].values():
        player.pop("hero", None)
        player.pop("cards", None)
    data["players"][pos]["hero"] = True
    data["players"][pos]["cards"] = list(cards)
    data["players"][pos]["fold"] = False
    data["players"][pos]["chips"] = chips


def test_unopened_utg_aa_open_raise():
    data = _base()

    for pos in ["MP", "CO", "BTN"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "UTG", cards=("A_spades", "A_hearts"), chips=False)

    decision = solve_clear_json(data)

    assert decision.node_type == "unopened"
    assert decision.raw_action == "open_raise"
    assert decision.click_sequence == ["Raise"]
    assert decision.debug["range_source"] == "rfi.UTG"


def test_unopened_utg_72o_fold():
    data = _base()

    for pos in ["MP", "CO", "BTN"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "UTG", cards=("7_spades", "2_hearts"), chips=False)

    decision = solve_clear_json(data)

    assert decision.node_type == "unopened"
    assert decision.raw_action == "fold"
    assert decision.click_sequence == ["FOLD"]
    assert decision.debug["range_fallback_used"] is True


def test_bb_vs_mp_limp_j7o_checks_from_range_default():
    data = _base()

    decision = solve_clear_json(data)

    assert decision.node_type == "bb_option_vs_1_limper"
    assert decision.hand_class == "J7o"
    assert decision.raw_action == "check"
    assert decision.click_sequence == ["Check"]
    assert decision.debug["range_source"] == "iso_raise.BB"


def test_bb_vs_mp_limp_ajs_iso_raises():
    data = _base()
    data["players"]["BB"]["cards"] = ["A_spades", "J_spades"]

    decision = solve_clear_json(data)

    assert decision.node_type == "bb_option_vs_1_limper"
    assert decision.hand_class == "AJs"
    assert decision.raw_action == "iso_raise"
    assert decision.click_sequence == ["98%", "Raise"]
    assert decision.size_pct == 98.0


def test_sb_first_in_aqs_raises():
    data = _base()

    for pos in ["UTG", "MP", "CO", "BTN"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "SB", cards=("A_spades", "Q_spades"), chips=0.5)

    decision = solve_clear_json(data)

    assert decision.node_type == "sb_first_in"
    assert decision.raw_action == "open_raise"
    assert decision.click_sequence == ["Raise"]


def test_sb_first_in_72o_limp_or_fold_by_range():
    data = _base()

    for pos in ["UTG", "MP", "CO", "BTN"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "SB", cards=("7_spades", "2_hearts"), chips=0.5)

    decision = solve_clear_json(data)

    assert decision.node_type == "sb_first_in"
    assert decision.raw_action in {"limp", "fold"}
    assert decision.click_sequence in (["CALL"], ["FOLD"])


def test_btn_iso_aqo_vs_limp_uses_98_raise():
    data = _base()

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "BTN", cards=("A_spades", "Q_hearts"), chips=False)

    decision = solve_clear_json(data)

    assert decision.node_type == "iso_vs_1_limper"
    assert decision.raw_action == "iso_raise"
    assert decision.click_sequence == ["98%", "Raise"]
