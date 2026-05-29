from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_24_snapshot_live_runtime_e2e.py"


def test_v2_24_snapshot_live_runtime_e2e_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)
    assert report["schema"] == "pokervision_solver_preflop_v224_snapshot_live_runtime_e2e_v1"
    assert report["status"] == "ok"
    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False
    assert all(report["checks"].values())

    case = report["case"]
    assert case["bridge_status"] == "ok"
    assert case["runtime_solver_source"] == "PokerVision_Solver_Preflop"
    assert case["runtime_solver_status"] == "ok"
    assert case["runtime_solver_action"] == "bet_raise"
    assert case["runtime_solver_raw_action"] in {
        "raise",
        "open_raise",
        "iso_raise",
        "3bet",
        "4bet",
        "5bet",
        "jam",
        "all_in",
    }
    assert not str(case["runtime_decision_id"]).startswith("v12_stub_")
    assert not str(case["runtime_decision_id"]).startswith("v12_fallback_")
    assert case["click_status"] == "dry_run"
    assert case["target_sequence"]
    assert case["click_points_count"] == len(case["target_sequence"])
