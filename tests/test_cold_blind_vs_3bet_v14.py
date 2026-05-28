import json
from pathlib import Path

from solver_preflop import solve_clear_json


def test_table_01_snapshot_sb_blind_vs_open_and_3bet_classifies_as_cold_vs_3bet():
    path = (
        Path("external")
        / "PokerVisionFinalVersionNoSolver_snapshot"
        / "PokerVision V1_2"
        / "outputs"
        / "ui_display_cycle"
        / "current_cycle"
        / "Clear_JSON_Pending"
        / "table_01"
        / "table_01_hand_21_preflop.pending.json"
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    decision = solve_clear_json(data)

    assert decision.hero_position == "SB"
    assert decision.hand_class == "T7o"
    assert decision.node_type == "cold_vs_3bet_or_higher"
    assert decision.debug["opener_pos"] == "UTG"
    assert decision.debug["three_bettor_pos"] == "CO"
    assert decision.debug["hero_commitment_bb"] == 0.5
    assert decision.debug["to_call_bb"] == 8.5
    assert decision.debug["raise_levels"] == [3.0, 9.0]

    # V1.5 wires cold_vs_3bet_or_higher into cold_4bet chart.
    # T7o is not in call/4bet ranges, so it is a normal fold, not safe_fallback.
    assert decision.status == "ok"
    assert decision.raw_action == "fold"
    assert decision.engine_action == "fold"
    assert decision.click_sequence == ["FOLD"]
    assert decision.debug["range_source"] == "cold_4bet.UTG|CO|SB"


def test_synthetic_bb_blind_vs_open_and_3bet_classifies_as_cold_vs_3bet():
    path = Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    # Hero remains BB with 1bb blind.
    data["frame_id"] = "synthetic_bb_cold_vs_3bet_preflop"

    data["players"]["UTG"]["fold"] = False
    data["players"]["UTG"]["chips"] = 3.0

    data["players"]["MP"]["fold"] = True
    data["players"]["MP"]["chips"] = False

    data["players"]["CO"]["fold"] = False
    data["players"]["CO"]["chips"] = 9.0

    data["players"]["BTN"]["fold"] = True
    data["players"]["BTN"]["chips"] = False

    data["players"]["SB"]["fold"] = True
    data["players"]["SB"]["chips"] = False

    data["players"]["BB"]["fold"] = False
    data["players"]["BB"]["chips"] = 1.0

    decision = solve_clear_json(data)

    assert decision.hero_position == "BB"
    assert decision.node_type == "cold_vs_3bet_or_higher"
    assert decision.debug["opener_pos"] == "UTG"
    assert decision.debug["three_bettor_pos"] == "CO"
    assert decision.debug["hero_commitment_bb"] == 1.0
    assert decision.debug["to_call_bb"] == 8.0

    # V1.5 uses cold_4bet chart for blind-only cold spots too.
    # Js7c is not in a continue range, so the decision is a normal fold.
    assert decision.status == "ok"
    assert decision.raw_action == "fold"
    assert decision.engine_action == "fold"
    assert decision.click_sequence == ["FOLD"]
    assert decision.debug["range_source"] == "cold_4bet.UTG|CO|BB"
