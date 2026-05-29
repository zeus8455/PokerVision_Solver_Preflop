from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = "pokervision_solver_preflop_v230_duplicate_active_runtime_retry_audit_v1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DISPLAY = SNAPSHOT_ROOT / "display_analysis_cycle.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _line_no(text: str, needle: str) -> int:
    idx = text.find(needle)
    if idx < 0:
        return -1
    return text[:idx].count("\n") + 1


def _run_static_import_check() -> subprocess.CompletedProcess[str]:
    code = "import display_analysis_cycle as d; print('ok')"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(SNAPSHOT_ROOT),
        text=True,
        capture_output=True,
        timeout=30,
    )


def build_report() -> dict[str, Any]:
    text = _read(DISPLAY)

    marker = "V2.30: recover duplicate Active into runtime retry when no runtime/final artifact exists"
    retry_reason = "v230_duplicate_active_runtime_retry_without_completed_runtime"
    retry_log = "V2.30 duplicate Active runtime retry enabled"
    duplicate_log = "duplicate Active action suppressed"
    runtime_candidate = "action_runtime_candidate = ("
    hard_stop = "duplicate_active_hard_stop_before_pending = ("

    import_check = _run_static_import_check()

    marker_line = _line_no(text, marker)
    duplicate_log_line = _line_no(text, duplicate_log)
    runtime_candidate_line = _line_no(text, runtime_candidate)
    hard_stop_line = _line_no(text, hard_stop)

    checks = {
        "display_file_exists": DISPLAY.exists(),
        "replace_import_present": "from dataclasses import dataclass, field, replace" in text,
        "v230_marker_present": marker in text,
        "v230_retry_reason_present": retry_reason in text,
        "v230_retry_log_present": retry_log in text,
        "checks_runtime_plan_dir": "v230_runtime_plan_dir = cycle_dir / V07_ACTION_RUNTIME_PLAN_DIR_NAME / slot.table_id" in text,
        "checks_final_clear_dir": "v230_final_clear_dir = cycle_dir / V04_CLEAR_JSON_FINAL_DIR_NAME / slot.table_id" in text,
        "requires_no_runtime_plan": "and not bool(v230_has_runtime_plan)" in text,
        "requires_no_final_clear": "and not bool(v230_has_final_clear)" in text,
        "limited_to_duplicate_active_blocked": 'str(action_event_decision.reason) == "duplicate_active_frame_blocked"' in text,
        "uses_dataclass_replace": "action_event_decision = replace(" in text,
        "sets_should_process_true": "should_process=True" in text,
        "sets_retry_event_id": "action_event_id=v230_retry_event_id" in text,
        "v230_before_runtime_candidate": marker_line > 0 and runtime_candidate_line > 0 and marker_line < runtime_candidate_line,
        "v230_before_duplicate_hard_stop": marker_line > 0 and hard_stop_line > 0 and marker_line < hard_stop_line,
        "v230_after_duplicate_suppression_log": duplicate_log_line > 0 and marker_line > duplicate_log_line,
        "display_import_ok": import_check.returncode == 0 and import_check.stdout.strip() == "ok",
        "display_import_no_traceback": "Traceback" not in import_check.stderr,
    }

    return {
        "schema": SCHEMA,
        "status": "ok" if all(checks.values()) else "failed",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "display_analysis_cycle": str(DISPLAY),
        "real_project_touched": False,
        "line_positions": {
            "duplicate_log": duplicate_log_line,
            "v230_marker": marker_line,
            "action_runtime_candidate": runtime_candidate_line,
            "duplicate_hard_stop": hard_stop_line,
        },
        "checks": checks,
        "import_stdout": import_check.stdout.strip(),
        "import_stderr": import_check.stderr.strip(),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
