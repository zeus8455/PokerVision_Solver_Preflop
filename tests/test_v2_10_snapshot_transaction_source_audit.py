from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_10_snapshot_transaction_source_audit.py"


def test_v2_10_snapshot_transaction_source_audit_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v210_snapshot_transaction_source_audit_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["static_checks"].values())

    assert report["scenario_count"] == 9
    assert report["ok_count"] == 9
    assert report["bad_count"] == 0

    cases = {item["scenario"]: item for item in report["cases"]}

    expected = {
        "action_button_dry_run_completed": (True, "completed", "click_cycle_completed", "action_button", True),
        "action_button_clicked_completed": (True, "completed", "click_cycle_completed", "action_button", True),
        "action_button_confirmed_completed": (True, "completed", "click_cycle_completed", "action_button", True),
        "action_button_skipped_pending": (False, "pending", "click_cycle_not_completed", "action_button", False),
        "action_button_blocked_failed": (False, "failed", "click_cycle_not_completed", "action_button", False),
        "service_dry_run_completed": (True, "completed", "click_cycle_completed", "service", True),
        "service_blocked_overrides_action_dry_run": (False, "failed", "click_cycle_not_completed", "service", False),
        "dry_run_not_completed_when_config_false": (False, "failed", "click_cycle_not_completed", "action_button", False),
        "no_open_transaction_reports_skipped_but_completed_signal_can_exist": (True, "skipped", "no_open_transaction", "action_button", True),
    }

    assert set(cases) == set(expected)

    for name, (
        click_completed,
        status,
        reason,
        branch,
        click_result_available,
    ) in expected.items():
        case = cases[name]
        assert case["ok"] is True

        report_payload = case["transaction_report"]
        assert report_payload["click_completed"] is click_completed
        assert report_payload["status"] == status
        assert report_payload["reason"] == reason
        assert report_payload["click_result"]["branch"] == branch

        derived = case["derived_display_cycle_inputs"]
        assert derived["clear_json_save_allowed"] is click_completed
        assert derived["click_result_for_clear_available"] is click_result_available

    assert cases["service_blocked_overrides_action_dry_run"]["transaction_report"]["click_result"]["branch"] == "service"
    assert cases["dry_run_not_completed_when_config_false"]["dry_run_counts_as_completed"] is False
