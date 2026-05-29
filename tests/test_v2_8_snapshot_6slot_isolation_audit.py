from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_8_snapshot_6slot_isolation_audit.py"


def test_v2_8_snapshot_6slot_isolation_audit_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v28_snapshot_6slot_isolation_audit_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert report["source_preflop_files_count"] == 4
    assert report["synthetic_6slot_cases"] is True
    assert report["files_total"] == 6
    assert report["ok_count"] == 6
    assert report["bad_count"] == 0
    assert report["published_runtime_files_count"] == 6
    assert report["published_final_clear_files_count"] == 6

    slot_checks = report["slot_checks"]
    assert all(slot_checks.values())

    expected_table_ids = [f"table_{index:02d}" for index in range(1, 7)]
    result_table_ids = [item["table_id"] for item in report["results"]]
    assert result_table_ids == expected_table_ids

    decision_ids = [item["decision_id"] for item in report["results"]]
    assert len(set(decision_ids)) == 6

    for item in report["results"]:
        table_id = item["table_id"]

        assert item["ok"] is True
        assert item["selected_source"] == "Solver_Preflop_Bridge"
        assert item["selection_reason"] == "v20_solver_preflop_selected"

        assert item["pending_validation"]["ok"] is True
        assert item["pending_runtime_plan"]["status"] == "preview_not_saved_pending_only"
        assert item["pending_runtime_plan"]["file_publication_enabled"] is False

        assert item["final_runtime_plan"]["status"] == "saved"
        assert item["final_runtime_plan"]["file_publication_enabled"] is True
        assert f"Action_Runtime_Plan_JSON\\{table_id}\\" in item["final_runtime_plan"]["path"]

        assert item["click_execution_guard"]["status"] == "dry_run"
        assert item["click_execution_guard"]["reason"] == "all_click_execution_guards_passed"
        assert item["click_execution_guard"]["guard_passed"] is True

        assert item["final_clear"]["validation"]["ok"] is True
        assert item["final_clear"]["exists"] is True
        assert item["final_clear"]["saved_frame_id"].startswith(table_id)
        assert item["final_clear"]["saved_table_id"] is None
        assert item["final_clear"]["saved_slot_bbox"] is None
        assert item["final_clear"]["synthetic_guard_slot_bbox"] == item["slot_bbox"]
        assert f"Clear_JSON\\{table_id}\\" in item["final_clear"]["path"]

        checks = item["checks"]
        assert all(checks.values())
