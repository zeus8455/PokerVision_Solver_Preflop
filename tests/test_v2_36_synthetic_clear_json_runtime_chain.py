from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_36_synthetic_clear_json_runtime_chain.py"


def test_v2_36_synthetic_clear_json_runtime_chain_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_36_synthetic_clear_json_runtime_chain.json"
    out_dir = tmp_path / "v2_36_outputs"

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--report-json",
            str(report_path),
            "--out-dir",
            str(out_dir),
        ],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert report_path.exists(), completed.stdout + completed.stderr

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["physical_click_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["screen_capture_executed"] is False

    results = {item["case_id"]: item for item in report["results"]}

    for case_id in [
        "fold_unopened_co_72o",
        "call_btn_vs_utg_open_88",
        "check_bb_vs_sb_limp_j7o",
        "open_raise_co_ako",
        "iso_raise_btn_ako",
        "threebet_bb_vs_btn_open_ako",
        "fourbet_co_vs_btn_3bet_ako",
        "fivebet_jam_bb_vs_btn_4bet_ako",
    ]:
        item = results[case_id]
        runtime = item["runtime"]
        final_publication = item["final_publication"]
        assert item["bridge_status"] == "ok"
        assert runtime["solver_source"] == "PokerVision_Solver_Preflop"
        assert runtime["click_status"] == "clicked"
        assert runtime["mouse_spy_called"] is True
        assert runtime["gate_status"] == "CONTROLLED_LIVE_CLICK_GATE_PASSED"
        assert final_publication["status"] == "saved"
        assert final_publication["saved_click_result_status"] == "clicked"

    assert results["open_raise_co_ako"]["runtime"]["click_target_sequence"] == ["Bet/Raise"]
    assert results["iso_raise_btn_ako"]["runtime"]["click_target_sequence"] == ["98%", "Bet/Raise"]
    assert results["threebet_bb_vs_btn_open_ako"]["runtime"]["click_target_sequence"] == ["98%", "Bet/Raise"]
    assert results["fourbet_co_vs_btn_3bet_ako"]["runtime"]["click_target_sequence"] == ["50%", "Bet/Raise"]
    assert results["fivebet_jam_bb_vs_btn_4bet_ako"]["runtime"]["click_target_sequence"] == ["98%", "Bet/Raise"]

    missing = results["missing_bet_raise_button_blocks"]
    assert missing["runtime"]["click_status"] == "blocked"
    assert missing["runtime"]["mouse_spy_called"] is False
    assert missing["final_publication"]["status"] == "skipped"

    assert results["postflop_clear_json_skipped"]["bridge_status"] == "skipped"
    assert results["postflop_clear_json_skipped"]["bridge_reason"] == "street_is_not_preflop"
    assert results["postflop_clear_json_skipped"]["runtime_called"] is False

    assert results["already_has_click_result_skipped"]["bridge_status"] == "skipped"
    assert results["already_has_click_result_skipped"]["bridge_reason"] == "clear_json_already_has_click_result"
    assert results["already_has_click_result_skipped"]["runtime_called"] is False
