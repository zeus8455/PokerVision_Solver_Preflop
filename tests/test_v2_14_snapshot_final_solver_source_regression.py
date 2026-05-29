from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_14_snapshot_final_solver_source_regression.py"


def test_v2_14_snapshot_final_solver_source_regression_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v214_snapshot_final_solver_source_regression_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["checks"].values())

    final_source_reports = report["final_source_reports"]
    assert set(final_source_reports) == {
        "dry_run_completed_final_saved",
        "clicked_completed_final_saved",
    }

    for item in final_source_reports.values():
        assert item["solver_bridge_status"] == "ok"
        assert item["solver_bridge_reason"] is None
        assert item["runtime_selected_source"] == "Solver_Preflop_Bridge"
        assert item["runtime_selection_reason"] == "v20_solver_preflop_selected"
        assert item["solver_action_decision_available"] is True
        assert item["adapted_to_legacy_action_decision"] is True
        assert item["decision_id"]
        assert item["solver_fingerprint"]
        assert item["source_frame_id"]
        assert item["runtime_plan_status"] == "saved"
        assert item["runtime_plan_publication_stage"] == "final"
        assert item["runtime_plan_file_publication_enabled"] is True
