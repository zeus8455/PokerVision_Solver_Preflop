import json
from pathlib import Path

from solver_preflop import solve_clear_json


def _table_01_snapshot_data():
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
    return json.loads(path.read_text(encoding="utf-8"))


def test_table_01_cold_vs_3bet_uses_cold_4bet_chart_and_folds_t7o():
    decision = solve_clear_json(_table_01_snapshot_data())

    assert decision.node_type == "cold_vs_3bet_or_higher"
    assert decision.hero_position == "SB"
    assert decision.hand_class == "T7o"
    assert decision.status == "ok"
    assert decision.raw_action == "fold"
    assert decision.engine_action == "fold"
    assert decision.click_sequence == ["FOLD"]
    assert decision.debug["range_source"] == "cold_4bet.UTG|CO|SB"
    assert decision.debug["range_fallback_used"] is True
    assert decision.debug["matched_range"] is None


def test_synthetic_sb_cold_vs_3bet_with_kk_returns_4bet():
    data = _table_01_snapshot_data()
    data["frame_id"] = "synthetic_sb_cold_vs_3bet_kk_preflop"

    # Force HERO to KK while preserving the table_01 spot:
    # UTG open 3bb, CO 3bet 9bb, Hero SB blind-only 0.5bb.
    data["players"]["SB"]["cards"] = ["Kh", "Kd"]

    decision = solve_clear_json(data)

    assert decision.node_type == "cold_vs_3bet_or_higher"
    assert decision.hero_position == "SB"
    assert decision.hand_class == "KK"
    assert decision.status == "ok"
    assert decision.raw_action == "4bet"
    assert decision.engine_action == "raise"
    assert decision.size_pct == 50.0
    assert decision.click_sequence == ["50%", "Raise"]
    assert decision.debug["range_source"] == "cold_4bet.UTG|CO|SB"
    assert decision.debug["matched_range"] == "KK+ AKs AKo"


def test_synthetic_sb_cold_vs_3bet_with_qq_returns_call_for_utg_co_sb():
    data = _table_01_snapshot_data()
    data["frame_id"] = "synthetic_sb_cold_vs_3bet_qq_preflop"
    data["players"]["SB"]["cards"] = ["Qh", "Qd"]

    decision = solve_clear_json(data)

    assert decision.node_type == "cold_vs_3bet_or_higher"
    assert decision.hero_position == "SB"
    assert decision.hand_class == "QQ"
    assert decision.status == "ok"
    assert decision.raw_action == "call"
    assert decision.engine_action == "call"
    assert decision.click_sequence == ["CALL"]
    assert decision.debug["range_source"] == "cold_4bet.UTG|CO|SB"
    assert decision.debug["matched_range"] == "QQ"
