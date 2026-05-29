from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
MAIN = SNAPSHOT_ROOT / "main.py"


def main() -> int:
    result = subprocess.run(
        [sys.executable, str(MAIN), "--startup-audit-only"],
        cwd=str(SNAPSHOT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    stdout = result.stdout
    stderr = result.stderr
    combined = stdout + "\n" + stderr

    checks = {
        "returncode_zero": result.returncode == 0,
        "startup_audit_only_enabled": "[V83_STARTUP_AUDIT_ONLY] enabled=True" in stdout,
        "live_ui_launch_skipped": "[V83_STARTUP_AUDIT_ONLY] live UI launch skipped" in stdout,
        "readiness_safe_no_click": "[V10_REAL_CLICK_READINESS] status=safe_no_click ok=True real_click_ready=False" in stdout,
        "action_real_click_disabled": "[ACTION_REAL_CLICK] enabled=False, dry_run=True" in stdout,
        "service_real_click_disabled": "[SERVICE_REAL_CLICK] enabled=False, dry_run=True" in stdout,
        "live_capture_guard_present": "[LIVE_CAPTURE_GUARD] real mouse/service clicks are disabled; data capture only" in stdout,
        "real_click_master_not_armed": "[V09_REAL_CLICK_GUARD] master armed is False; physical clicks remain impossible" in stdout,
        "no_traceback": "Traceback" not in combined,
        "no_startup_abort": "Startup aborted" not in combined,
    }

    report = {
        "schema": "pokervision_solver_preflop_v218_startup_audit_only_readiness_v1",
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "main": str(MAIN),
        "returncode": result.returncode,

        "real_project_touched": False,
        "live_ui_launched": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,

        "checks": checks,
        "stdout_tail": stdout.splitlines()[-12:],
        "stderr": stderr,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
