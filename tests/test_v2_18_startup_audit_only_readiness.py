from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_18_startup_audit_only_readiness.py"


def test_v2_18_startup_audit_only_readiness_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v218_startup_audit_only_readiness_v1"
    assert report["status"] == "ok"

    assert report["returncode"] == 0

    assert report["real_project_touched"] is False
    assert report["live_ui_launched"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert all(report["checks"].values())

    tail = "\n".join(report["stdout_tail"])

    assert "[ACTION_REAL_CLICK] enabled=False, dry_run=True" in tail
    assert "[SERVICE_REAL_CLICK] enabled=False, dry_run=True" in tail
    assert "[V10_REAL_CLICK_READINESS] status=safe_no_click ok=True real_click_ready=False" in tail
    assert "[V83_STARTUP_AUDIT_ONLY] enabled=True" in tail
    assert "[V83_STARTUP_AUDIT_ONLY] live UI launch skipped" in tail

    assert report["stderr"] == ""
