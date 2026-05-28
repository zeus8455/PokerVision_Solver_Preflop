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


def _clear_non_blinds(data):
    for pos in ["UTG", "MP", "CO", "BTN"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False


def test_btn_vs_co_open_aqo_3bets():
    data = _base()
    data["players"]["UTG"]["fold"] = True
    data["players"]["UTG"]["chips"] = False
    data["players"]["MP"]["fold"] = True
    data["players"]["MP"]["chips"] = False
    data["players"]["CO"]["fold"] = False
    data["players"]["CO"]["chips"] = 2.5

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "BTN", cards=("A_spades", "Q_hearts"), chips=False)

    decision = solve_clear_json(data)

    assert decision.node_type == "facing_open"
    assert decision.raw_action == "3bet"
    assert decision.click_sequence == ["98%", "Raise"]
    assert decision.debug["range_source"] == "vs_open.CO|BTN"


def test_btn_vs_co_open_76s_calls():
    data = _base()
    data["players"]["UTG"]["fold"] = True
    data["players"]["UTG"]["chips"] = False
    data["players"]["MP"]["fold"] = True
    data["players"]["MP"]["chips"] = False
    data["players"]["CO"]["fold"] = False
    data["players"]["CO"]["chips"] = 2.5

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "BTN", cards=("7_spades", "6_spades"), chips=False)

    decision = solve_clear_json(data)

    assert decision.node_type == "facing_open"
    assert decision.raw_action == "call"
    assert decision.click_sequence == ["CALL"]


def test_btn_vs_co_open_72o_folds():
    data = _base()
    data["players"]["UTG"]["fold"] = True
    data["players"]["UTG"]["chips"] = False
    data["players"]["MP"]["fold"] = True
    data["players"]["MP"]["chips"] = False
    data["players"]["CO"]["fold"] = False
    data["players"]["CO"]["chips"] = 2.5

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "BTN", cards=("7_spades", "2_hearts"), chips=False)

    decision = solve_clear_json(data)

    assert decision.node_type == "facing_open"
    assert decision.raw_action == "fold"
    assert decision.click_sequence == ["FOLD"]


def test_mp_limper_vs_btn_iso_qq_3bets():
    data = _base()

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "MP", cards=("Q_spades", "Q_hearts"), chips=1.0)

    data["players"]["UTG"]["fold"] = True
    data["players"]["UTG"]["chips"] = False
    data["players"]["CO"]["fold"] = True
    data["players"]["CO"]["chips"] = False
    data["players"]["BTN"]["fold"] = False
    data["players"]["BTN"]["chips"] = 4.5

    decision = solve_clear_json(data)

    assert decision.node_type == "limper_vs_iso"
    assert decision.raw_action == "3bet"
    assert decision.click_sequence == ["98%", "Raise"]


def test_mp_limper_vs_btn_iso_kqo_calls():
    data = _base()

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "MP", cards=("K_spades", "Q_hearts"), chips=1.0)

    data["players"]["UTG"]["fold"] = True
    data["players"]["UTG"]["chips"] = False
    data["players"]["CO"]["fold"] = True
    data["players"]["CO"]["chips"] = False
    data["players"]["BTN"]["fold"] = False
    data["players"]["BTN"]["chips"] = 4.5

    decision = solve_clear_json(data)

    assert decision.node_type == "limper_vs_iso"
    assert decision.raw_action == "call"
    assert decision.click_sequence == ["CALL"]


def test_co_opener_vs_small_3bet_ajo_calls_by_override():
    data = _base()

    for pos in ["UTG", "MP"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "CO", cards=("A_spades", "J_hearts"), chips=2.0)

    data["players"]["BTN"]["fold"] = False
    data["players"]["BTN"]["chips"] = 4.0

    decision = solve_clear_json(data)

    assert decision.node_type == "opener_vs_small_3bet"
    assert decision.raw_action == "call"
    assert "small_3bet_override" in decision.debug["range_source"]


def test_co_opener_vs_normal_3bet_ajo_folds():
    data = _base()

    for pos in ["UTG", "MP", "BTN"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "CO", cards=("A_spades", "J_hearts"), chips=2.5)

    data["players"]["SB"]["fold"] = False
    data["players"]["SB"]["chips"] = 8.0

    decision = solve_clear_json(data)

    assert decision.node_type == "opener_vs_normal_3bet"
    assert decision.raw_action == "fold"
    assert decision.click_sequence == ["FOLD"]


def test_co_opener_vs_normal_3bet_aqs_4bets():
    data = _base()

    for pos in ["UTG", "MP", "BTN"]:
        data["players"][pos]["fold"] = True
        data["players"][pos]["chips"] = False

    data["players"]["BB"].pop("hero", None)
    data["players"]["BB"].pop("cards", None)
    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    _move_hero(data, "CO", cards=("A_spades", "Q_spades"), chips=2.5)

    data["players"]["SB"]["fold"] = False
    data["players"]["SB"]["chips"] = 8.0

    decision = solve_clear_json(data)

    assert decision.node_type == "opener_vs_normal_3bet"
    assert decision.raw_action == "4bet"
    assert decision.click_sequence == ["50%", "Raise"]


def test_btn_threebettor_vs_sb_4bet_aks_5bet_jam():
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
    data["players"]["SB"]["chips"] = 20.0

    decision = solve_clear_json(data)

    assert decision.node_type == "threebettor_vs_normal_4bet"
    assert decision.raw_action == "5bet_jam"
    assert decision.click_sequence == ["98%", "Raise"]
