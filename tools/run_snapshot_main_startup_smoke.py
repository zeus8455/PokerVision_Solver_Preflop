from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
SNAPSHOT_MAIN = SNAPSHOT_ROOT / "main.py"
SNAPSHOT_DISPLAY = SNAPSHOT_ROOT / "display_analysis_cycle.py"
SNAPSHOT_BRIDGE = SNAPSHOT_ROOT / "runtime" / "solver_preflop_dryrun_bridge.py"


REQUIRED_DISPLAY_SNIPPETS = {
    "bridge_import": "from runtime.solver_preflop_dryrun_bridge import build_solver_preflop_dryrun_bridge_contract",
    "publication_toggle": "V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES = False",
    "bridge_call": "solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(",
    "toggle_call": "publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES)",
    "contract_embedding": 'action_decision_contract["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract',
    "state_embedding": 'state["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract',
}


def _static_display_checks() -> dict[str, bool]:
    text = SNAPSHOT_DISPLAY.read_text(encoding="utf-8")
    return {name: snippet in text for name, snippet in REQUIRED_DISPLAY_SNIPPETS.items()}


def _static_bridge_checks() -> dict[str, bool]:
    text = SNAPSHOT_BRIDGE.read_text(encoding="utf-8")
    return {
        "bridge_exists": SNAPSHOT_BRIDGE.exists(),
        "can_find_solver_by_parent": "_find_solver_project_root" in text,
        "has_solver_import_guard": "_ensure_solver_importable" in text,
        "calls_solve_clear_json": "solve_clear_json" in text,
        "builds_pokervision_bridge_payload": "build_pokervision_bridge_payload" in text,
    }


def _run_snapshot_main_startup_audit() -> dict:
    env = os.environ.copy()
    env["POKERVISION_SOLVER_PREFLOP_ROOT"] = str(PROJECT_ROOT)

    completed = subprocess.run(
        [sys.executable, str(SNAPSHOT_MAIN), "--startup-audit-only"],
        cwd=SNAPSHOT_ROOT,
        text=True,
        capture_output=True,
        env=env,
    )

    stdout_lines = completed.stdout.splitlines()
    stderr_lines = completed.stderr.splitlines()

    return {
        "returncode": completed.returncode,
        "stdout_tail": stdout_lines[-40:],
        "stderr_tail": stderr_lines[-40:],
        "startup_audit_only_seen": any("[V83_STARTUP_AUDIT_ONLY] enabled=True" in line for line in stdout_lines),
        "live_ui_skipped_seen": any("[V83_STARTUP_AUDIT_ONLY] live UI launch skipped" in line for line in stdout_lines),
        "live_output_cleanup_seen": any("[LIVE_OUTPUT_CLEANUP]" in line for line in stdout_lines),
    }


def main() -> int:
    if not SNAPSHOT_ROOT.exists():
        raise FileNotFoundError(SNAPSHOT_ROOT)
    if not SNAPSHOT_MAIN.exists():
        raise FileNotFoundError(SNAPSHOT_MAIN)
    if not SNAPSHOT_DISPLAY.exists():
        raise FileNotFoundError(SNAPSHOT_DISPLAY)
    if not SNAPSHOT_BRIDGE.exists():
        raise FileNotFoundError(SNAPSHOT_BRIDGE)

    display_checks = _static_display_checks()
    bridge_checks = _static_bridge_checks()
    startup = _run_snapshot_main_startup_audit()

    ok = (
        all(display_checks.values())
        and all(bridge_checks.values())
        and startup["returncode"] == 0
        and startup["startup_audit_only_seen"]
        and startup["live_ui_skipped_seen"]
        and not startup["live_output_cleanup_seen"]
    )

    report = {
        "schema": "pokervision_solver_preflop_snapshot_main_startup_smoke_v1",
        "status": "ok" if ok else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "snapshot_main": str(SNAPSHOT_MAIN),
        "snapshot_display": str(SNAPSHOT_DISPLAY),
        "snapshot_bridge": str(SNAPSHOT_BRIDGE),
        "real_project_touched": False,
        "display_checks": display_checks,
        "bridge_checks": bridge_checks,
        "startup_audit": startup,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
