from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_21_real_click_stub_blocker_audit.py"


def test_v2_21_real_click_stub_blocker_audit_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v221_real_click_stub_blocker_audit_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["checks"].values())

    checks = report["checks"]

    assert checks["v87_full_scope_sets_action_button_only_false"] is True
    assert checks["v87_full_scope_sets_simple_actions_only_false"] is True
    assert checks["v87_full_scope_enables_raise_branch"] is True
    assert checks["v87_full_scope_no_limit_clicks"] is True
    assert checks["v87_full_scope_allows_raise_actions"] is True
    assert checks["v87_full_scope_allows_raise_buttons"] is True

    assert checks["runtime_imports_real_click_flags"] is True
    assert checks["runtime_detects_real_click_mode"] is True
    assert checks["runtime_blocks_stub_status"] is True
    assert checks["runtime_blocks_v12_stub_decision_id"] is True
    assert checks["runtime_block_reason_present"] is True
    assert checks["runtime_block_returns_no_click_completed"] is True
    assert checks["runtime_block_returns_guard_failed"] is True

    assert checks["v219_redirects_probe_stdout"] is True
    assert checks["v219_exposes_probe_stdout_lines"] is True

    assert checks["v220_real_live_readiness_tool_exists"] is True
    assert checks["v220_checks_real_click_ready"] is True
