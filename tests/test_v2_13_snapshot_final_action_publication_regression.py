from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_13_snapshot_final_action_publication_regression.py"


def test_v2_13_snapshot_final_action_publication_regression_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v213_snapshot_final_action_publication_regression_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["checks"].values())

    completed = report["completed_reports"]
    assert set(completed) == {
        "dry_run_completed_final_saved",
        "clicked_completed_final_saved",
    }

    for item in completed.values():
        assert item["final_clear_saved"] is True
        assert item["decision_json_status"] == "saved"
        assert item["decision_json_path"]
        assert item["action_decision_status"] == "saved"
        assert item["action_decision_path"]
        assert item["runtime_plan_status"] == "saved"
        assert item["runtime_plan_path"]
        assert item["runtime_plan_publication_stage"] == "final"
        assert item["runtime_plan_file_publication_enabled"] is True
        assert item["unexpected_keyword_error_absent"] is True
        assert item["name_error_absent"] is True

    assert report["next_known_gap"]["status"] == "known_gap_for_v214"
    assert report["next_known_gap"]["reason"]
