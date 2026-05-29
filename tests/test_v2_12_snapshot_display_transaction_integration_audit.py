from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_12_snapshot_display_transaction_integration_audit.py"


def test_v2_12_snapshot_display_transaction_integration_audit_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v212_snapshot_display_transaction_integration_audit_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["static_checks"].values())
    assert all(report["output_checks"].values())

    assert report["scenario_count"] == 6
    assert report["ok_count"] == 6
    assert report["bad_count"] == 0
    assert report["dark_files_count"] == 6
    assert report["pending_files_count"] == 4
    assert report["final_files_count"] == 2

    scenarios = {item["scenario"]: item for item in report["scenarios"]}

    expected_names = {
        "dry_run_completed_final_saved",
        "clicked_completed_final_saved",
        "skipped_runtime_pending_only",
        "blocked_runtime_pending_only",
        "not_active_dark_json_only",
        "hard_stop_before_pending_decision",
    }
    assert set(scenarios) == expected_names

    for item in scenarios.values():
        assert item["ok"] is True
        assert all(item["checks"].values())

    dry_run = scenarios["dry_run_completed_final_saved"]
    assert dry_run["transaction_runtime_report"]["click_completed"] is True
    assert dry_run["derived_display_inputs"]["clear_json_save_allowed"] is True
    assert dry_run["derived_display_inputs"]["click_result_for_clear_available"] is True
    assert dry_run["dark_json"]["clear_json_contract"]["status"] == "saved"
    assert dry_run["dark_json"]["clear_json_contract"]["publication_stage"] == "final"
    assert dry_run["final_clear_json"]["exists"] is True
    assert dry_run["final_clear_json"]["saved_click_result"]["status"] == "dry_run"

    clicked = scenarios["clicked_completed_final_saved"]
    assert clicked["transaction_runtime_report"]["click_completed"] is True
    assert clicked["derived_display_inputs"]["clear_json_save_allowed"] is True
    assert clicked["final_clear_json"]["exists"] is True
    assert clicked["final_clear_json"]["saved_click_result"]["status"] == "clicked"

    skipped = scenarios["skipped_runtime_pending_only"]
    assert skipped["transaction_runtime_report"]["click_completed"] is False
    assert skipped["derived_display_inputs"]["clear_json_save_allowed"] is False
    assert skipped["derived_display_inputs"]["click_result_for_clear_available"] is False
    assert skipped["dark_json"]["clear_json_contract"]["status"] == "skipped"
    assert skipped["dark_json"]["clear_json_contract"]["reason"] == "action_transaction_not_completed"
    assert skipped["dark_json"]["clear_json_contract"]["publication_stage"] == "pending_only"
    assert skipped["final_clear_json"]["exists"] is False

    blocked = scenarios["blocked_runtime_pending_only"]
    assert blocked["transaction_runtime_report"]["click_completed"] is False
    assert blocked["derived_display_inputs"]["clear_json_save_allowed"] is False
    assert blocked["dark_json"]["clear_json_contract"]["reason"] == "action_transaction_not_completed"
    assert blocked["final_clear_json"]["exists"] is False

    not_active = scenarios["not_active_dark_json_only"]
    assert not_active["dark_json"]["clear_json_contract"]["reason"] == "not_active_poker_state"
    assert not_active["dark_json"]["clear_json_contract"]["publication_stage"] == "dark_json_only"
    assert not_active["final_clear_json"]["exists"] is False

    hard_stop = scenarios["hard_stop_before_pending_decision"]
    assert hard_stop["dark_json"]["clear_json_contract"]["reason"] == "duplicate_active_frame_blocked"
    assert hard_stop["dark_json"]["clear_json_contract"]["publication_stage"] == "dark_json_only"
    assert hard_stop["dark_json"]["clear_json_contract"]["hard_stop_before_pending_decision"] is True
    assert hard_stop["final_clear_json"]["exists"] is False
