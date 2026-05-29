from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_17_pre_live_config_audit.py"


def test_v2_17_pre_live_config_audit_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v217_pre_live_config_audit_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["checks"].values())

    cfg = report["effective_config"]

    assert cfg["V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE"] is True
    assert cfg["V11_REAL_MOUSE_CLICK_ENABLED"] is False
    assert cfg["V11_CLICK_DRY_RUN"] is True
    assert cfg["V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED"] is False
    assert cfg["V11_TRIGGER_UI_SERVICE_DRY_RUN"] is True
    assert cfg["V09_REAL_CLICK_MASTER_ARMED"] is False

    assert cfg["V03_TABLE_ACTION_TRANSACTION_GATE_ENABLED"] is True
    assert cfg["V03_TRANSACTION_DRY_RUN_COUNTS_AS_COMPLETED"] is True
    assert cfg["V03_TRANSACTION_RELEASE_ON_INACTIVE"] is True

    assert cfg["V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT"] is True
    assert cfg["V07_ACTION_RUNTIME_PLAN_ENABLED"] is True

    assert cfg["V09_REQUIRE_SLOT_BOUNDARY_GUARD"] is True
    assert cfg["V09_REQUIRE_NO_REPEAT_DECISION_GUARD"] is True
    assert cfg["V09_REQUIRE_BUTTON_AVAILABILITY_GUARD"] is True
    assert cfg["V09_ALLOW_DRY_RUN_COMPLETION"] is True
    assert cfg["V09_BLOCK_REAL_CLICK_WHEN_LIVE_CAPTURE_NO_CLICK"] is True

    assert cfg["V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE"] is True
    assert cfg["V20_SOLVER_PREFLOP_DRY_RUN_ONLY"] is True
