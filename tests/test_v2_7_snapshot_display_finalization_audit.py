from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_7_snapshot_display_finalization_audit.py"


def test_v2_7_snapshot_display_finalization_audit_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v27_snapshot_display_finalization_audit_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert report["files_total"] == 4
    assert report["ok_count"] == 4
    assert report["bad_count"] == 0
    assert report["published_runtime_files_count"] == 4
    assert report["published_final_clear_files_count"] == 4

    static_checks = report["static_checks"]
    assert all(static_checks.values())

    for item in report["results"]:
        assert item["ok"] is True
        assert item["selected_source"] == "Solver_Preflop_Bridge"
        assert item["selection_reason"] == "v20_solver_preflop_selected"

        assert item["pending_runtime_plan"]["status"] == "preview_not_saved_pending_only"
        assert item["pending_runtime_plan"]["publication_stage"] == "pending_preview"
        assert item["pending_runtime_plan"]["file_publication_enabled"] is False
        assert item["pending_runtime_plan"]["path"] is None

        assert item["final_runtime_plan"]["status"] == "saved"
        assert item["final_runtime_plan"]["publication_stage"] == "final"
        assert item["final_runtime_plan"]["file_publication_enabled"] is True
        assert item["final_runtime_plan"]["path"]

        audit = item["central_finalization_audit"]
        assert audit["pending_validation_ok"] is True
        assert audit["click_result_received"] is True
        assert audit["click_execution_guard_called"] is True
        assert audit["click_execution_guard_passed"] is True
        assert audit["final_publication_blocked"] is False
        assert audit["state_machine_simulation"]["decision_should_save"] is True
        assert audit["state_machine_simulation"]["clear_state_to_save_exists"] is True

        checks = item["checks"]
        assert checks["solver_source_selected"] is True
        assert checks["pending_runtime_preview_expected"] is True
        assert checks["final_runtime_plan_saved"] is True
        assert checks["click_execution_guard_passed"] is True
        assert checks["compact_click_result_schema_safe"] is True
        assert checks["final_validation_ok"] is True
        assert checks["final_clear_saved"] is True
        assert checks["saved_final_contains_same_click_result"] is True
