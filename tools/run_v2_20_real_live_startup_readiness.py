from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
MAIN = SNAPSHOT_ROOT / "main.py"


def main() -> int:
    env = os.environ.copy()

    env["POKERVISION_CONTROLLED_LIVE_READY_PROFILE"] = "V8_1_CONTROLLED_ACTION_BUTTON"
    env["POKERVISION_CONTROLLED_LIVE_TEST_SCOPE"] = "V8_7_FULL_LIVE_CHAIN_NO_LIMIT"
    env["POKERVISION_CONTROLLED_LIVE_CLICK"] = "V3_1_ONE_CLICK"
    env["POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS"] = "table_01,table_02,table_03,table_04,table_05,table_06"
    env["POKERVISION_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN"] = "0"

    result = subprocess.run(
        [sys.executable, str(MAIN), "--startup-audit-only"],
        cwd=str(SNAPSHOT_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    stdout = result.stdout
    stderr = result.stderr
    combined = stdout + "\n" + stderr

    expected_lines = {
        "no_click_mode_disabled": "[V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE] False" in stdout,
        "master_armed": "[V09_REAL_CLICK_MASTER_ARMED] True" in stdout,
        "action_real_click_enabled": "[ACTION_REAL_CLICK] enabled=True, dry_run=False" in stdout,
        "service_real_click_enabled": "[SERVICE_REAL_CLICK] enabled=True, dry_run=False" in stdout,
        "readiness_ready": "[V10_REAL_CLICK_READINESS] status=ready_for_controlled_real_click ok=True real_click_ready=True" in stdout,
        "startup_audit_only": "[V83_STARTUP_AUDIT_ONLY] live UI launch skipped" in stdout,
    }

    checks = {
        "returncode_zero": result.returncode == 0,
        "no_traceback": "Traceback" not in combined,
        "no_startup_abort": "Startup aborted" not in combined,
        **expected_lines,
    }

    report = {
        "schema": "pokervision_solver_preflop_v220_real_live_startup_readiness_v1",
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "main": str(MAIN),
        "returncode": result.returncode,

        "env": {
            "POKERVISION_CONTROLLED_LIVE_READY_PROFILE": env["POKERVISION_CONTROLLED_LIVE_READY_PROFILE"],
            "POKERVISION_CONTROLLED_LIVE_TEST_SCOPE": env["POKERVISION_CONTROLLED_LIVE_TEST_SCOPE"],
            "POKERVISION_CONTROLLED_LIVE_CLICK": env["POKERVISION_CONTROLLED_LIVE_CLICK"],
            "POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS": env["POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS"],
            "POKERVISION_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN": env["POKERVISION_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN"],
        },

        "real_project_touched": False,
        "live_ui_launched": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "real_click_ready": expected_lines["readiness_ready"],

        "checks": checks,
        "stdout_tail": stdout.splitlines()[-20:],
        "stderr": stderr,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
