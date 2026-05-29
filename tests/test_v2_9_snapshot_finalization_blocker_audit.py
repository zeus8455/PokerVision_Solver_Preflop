from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_9_snapshot_finalization_blocker_audit.py"


def test_v2_9_snapshot_finalization_blocker_audit_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v29_snapshot_finalization_blocker_audit_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["static_checks"].values())

    assert report["scenario_count"] == 8
    assert report["ok_count"] == 8
    assert report["bad_count"] == 0

    matrix = report["matrix"]
    assert matrix["selected_source"] == "Solver_Preflop_Bridge"
    assert matrix["selection_reason"] == "v20_solver_preflop_selected"
    assert matrix["runtime_plan_status"] == "saved"
    assert matrix["ok"] is True

    scenarios = {item["scenario"]: item for item in matrix["scenarios"]}

    expected = {
        "pending_validation_failed": "pending_clear_json_contract_validation_failed",
        "action_transaction_not_completed": "action_transaction_not_completed",
        "missing_click_result_for_final_clear_json": "missing_click_result_for_final_clear_json",
        "click_execution_guard_failed": "click_execution_guard_failed",
        "final_publication_guard_duplicate_decision": "duplicate_click_result_reused",
        "state_machine_should_save_false": "duplicate_or_not_advanced",
        "final_clear_json_contract_validation_failed": "final_clear_json_contract_validation_failed",
        "success_final_clear_saved": "saved",
    }

    assert set(scenarios) == set(expected)

    for name, reason in expected.items():
        scenario = scenarios[name]
        assert scenario["ok"] is True
        assert scenario["expected_reason"] == reason
        assert scenario["actual_reason"] == reason

    assert scenarios["action_transaction_not_completed"]["publication_stage"] == "pending_only"
    assert scenarios["missing_click_result_for_final_clear_json"]["publication_stage"] == "pending_only"
    assert scenarios["click_execution_guard_failed"]["publication_stage"] == "pending_only"
    assert scenarios["state_machine_should_save_false"]["publication_stage"] == "pending_only"

    guard_extra = scenarios["click_execution_guard_failed"]["extra"]
    assert guard_extra["guard_status"] == "blocked"
    assert guard_extra["guard_reason"] == "missing_slot_bbox"
    assert guard_extra["guard_passed"] is False

    success = scenarios["success_final_clear_saved"]
    assert success["status"] == "saved"
    assert success["publication_stage"] == "final"
    assert success["extra"]["guard_status"] == "dry_run"
    assert success["extra"]["guard_reason"] == "all_click_execution_guards_passed"
    assert success["extra"]["guard_passed"] is True
    assert success["extra"]["validation"]["ok"] is True
    assert success["extra"]["path"]
