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


def test_facing_open_jam_guarded_fallback():
    data = _base()

    for pos in ["UTG", "CO"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["MP"]["fold"] = False
    data["players"]["MP"]["chips"] = 12.0
    data["players"]["MP"]["all_in"] = True

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "BTN", cards=("A_spades", "Q_hearts"), chips=False)

    decision = solve_clear_json(data)

    assert decision.status == "fallback"
    assert decision.node_type == "facing_open_jam"
    assert decision.click_sequence == ["Check", "Check/fold", "FOLD"]
    assert decision.debug["all_in_actor_pos"] == "MP"
    assert decision.debug["all_in_amount_bb"] == 12.0


def test_blind_vs_open_jam_guarded_fallback():
    data = _base()

    data["players"]["UTG"]["fold"] = True
    data["players"]["UTG"]["chips"] = False
    data["players"]["MP"]["fold"] = True
    data["players"]["MP"]["chips"] = False
    data["players"]["CO"]["fold"] = True
    data["players"]["CO"]["chips"] = False

    data["players"]["BTN"]["fold"] = False
    data["players"]["BTN"]["chips"] = 9.0
    data["players"]["BTN"]["all_in"] = True

    # Hero remains BB with 1bb committed.
    decision = solve_clear_json(data)

    assert decision.status == "fallback"
    assert decision.node_type == "blind_vs_open_jam"
    assert decision.debug["to_call_bb"] == 8.0
    assert decision.debug["all_in_actor_pos"] == "BTN"


def test_opener_vs_3bet_jam_guarded_fallback():
    data = _base()

    for pos in ["UTG", "MP"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "CO", cards=("A_spades", "J_hearts"), chips=2.5)

    data["players"]["BTN"]["fold"] = False
    data["players"]["BTN"]["chips"] = 18.0
    data["players"]["BTN"]["all_in"] = True

    decision = solve_clear_json(data)

    assert decision.status == "fallback"
    assert decision.node_type == "opener_vs_3bet_jam"
    assert decision.debug["three_bettor_pos"] == "BTN"
    assert decision.debug["all_in_is_full_raise"] is True


def test_opener_vs_incomplete_3bet_allin_guarded_fallback():
    data = _base()

    for pos in ["UTG", "MP"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "CO", cards=("A_spades", "J_hearts"), chips=2.5)

    data["players"]["BTN"]["fold"] = False
    data["players"]["BTN"]["chips"] = 3.0
    data["players"]["BTN"]["all_in"] = True

    decision = solve_clear_json(data)

    assert decision.status == "fallback"
    assert decision.node_type == "opener_vs_incomplete_3bet_allin"
    assert decision.debug["all_in_is_full_raise"] is False
    assert decision.debug["all_in_reopens_action"] is False


def test_threebettor_vs_4bet_jam_guarded_fallback():
    data = _base()

    for pos in ["UTG", "MP"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    data["players"]["CO"]["fold"] = False
    data["players"]["CO"]["chips"] = 2.5

    _move_hero(data, "BTN", cards=("A_spades", "K_spades"), chips=8.0)

    data["players"]["SB"]["fold"] = False
    data["players"]["SB"]["chips"] = 24.0
    data["players"]["SB"]["all_in"] = True

    decision = solve_clear_json(data)

    assert decision.status == "fallback"
    assert decision.node_type == "threebettor_vs_4bet_jam"
    assert decision.debug["four_bettor_pos"] == "SB"
    assert decision.debug["all_in_is_full_raise"] is True


def test_hero_already_allin_no_decision():
    data = _base()
    data["players"]["BB"]["all_in"] = True
    data["players"]["BB"]["chips"] = 1.0

    decision = solve_clear_json(data)

    assert decision.status == "fallback"
    assert decision.node_type == "hero_already_allin_no_decision"
    assert decision.click_sequence == ["Check", "Check/fold", "FOLD"]
