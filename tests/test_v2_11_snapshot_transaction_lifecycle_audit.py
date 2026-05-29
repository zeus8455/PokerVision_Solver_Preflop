from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_11_snapshot_transaction_lifecycle_audit.py"


def test_v2_11_snapshot_transaction_lifecycle_audit_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v211_snapshot_transaction_lifecycle_audit_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["static_checks"].values())

    assert report["scenario_count"] == 7
    assert report["ok_count"] == 7
    assert report["bad_count"] == 0

    scenarios = {item["scenario"]: item for item in report["scenarios"]}

    expected_names = {
        "full_success_lifecycle_releases_table",
        "early_duplicate_blocks_heavy_analysis",
        "late_duplicate_action_cycle_blocks",
        "skipped_runtime_pending_then_inactive_release",
        "blocked_runtime_failed_until_abort",
        "failed_active_finalization_release",
        "observe_inactive_without_release_keeps_lock",
    }
    assert set(scenarios) == expected_names

    for item in scenarios.values():
        assert item["ok"] is True
        assert all(item["checks"].values())

    success = scenarios["full_success_lifecycle_releases_table"]
    assert success["begin"]["phase"] == "analyzing"
    assert success["action"]["phase"] == "waiting_click"
    assert success["final"]["phase"] == "click_done"
    assert success["final"]["status"] == "completed"
    assert success["final"]["click_completed"] is True
    assert success["after_snapshot"] is None
    assert success["next_begin"]["should_process"] is True

    early_duplicate = scenarios["early_duplicate_blocks_heavy_analysis"]
    assert early_duplicate["second"]["should_process"] is False
    assert early_duplicate["second"]["reason"] == "table_lifecycle_already_open_before_analysis"
    assert early_duplicate["snapshot"]["phase"] == "analyzing"

    late_duplicate = scenarios["late_duplicate_action_cycle_blocks"]
    assert late_duplicate["second_action"]["should_process"] is False
    assert late_duplicate["second_action"]["reason"] == "table_action_transaction_already_open"
    assert late_duplicate["snapshot"]["phase"] == "waiting_click"

    skipped = scenarios["skipped_runtime_pending_then_inactive_release"]
    assert skipped["final"]["status"] == "pending"
    assert skipped["final"]["phase"] == "click_pending"
    assert skipped["final"]["click_completed"] is False
    assert skipped["inactive_release"]["status"] == "aborted"
    assert skipped["after_release_snapshot"] is None
    assert skipped["next_begin"]["should_process"] is True

    blocked = scenarios["blocked_runtime_failed_until_abort"]
    assert blocked["final"]["status"] == "failed"
    assert blocked["final"]["phase"] == "click_failed"
    assert blocked["second_action"]["should_process"] is False
    assert blocked["abort"]["status"] == "aborted"
    assert blocked["after_abort_snapshot"] is None
    assert blocked["next_begin"]["should_process"] is True

    release = scenarios["failed_active_finalization_release"]
    assert release["release"]["status"] == "aborted"
    assert release["release"]["reason"] == "active_runtime_plan_not_built"
    assert release["after_release_snapshot"] is None
    assert release["next_begin"]["should_process"] is True

    inactive_no_release = scenarios["observe_inactive_without_release_keeps_lock"]
    assert inactive_no_release["inactive"]["phase"] == "analyzing"
    assert inactive_no_release["snapshot"]["phase"] == "analyzing"
    assert inactive_no_release["blocked"]["should_process"] is False
