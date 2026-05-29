from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_22_strict_real_click_source_guard_audit.py"


def test_v2_22_strict_real_click_source_guard_audit_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v222_strict_real_click_source_guard_audit_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["checks"].values())

    checks = report["checks"]

    assert checks["captures_solver_source"] is True
    assert checks["captures_solver_status"] is True
    assert checks["blocks_non_solver_preflop_source"] is True
    assert checks["blocks_non_ok_solver_status"] is True
    assert checks["blocks_v12_stub_decision"] is True
    assert checks["blocks_v12_fallback_decision"] is True
    assert checks["reports_solver_source"] is True
    assert checks["reports_solver_status"] is True
