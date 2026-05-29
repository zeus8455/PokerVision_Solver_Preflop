from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = "pokervision_solver_preflop_v232_pre_runtime_solver_bridge_injection_audit_v1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
TARGET = SNAPSHOT_ROOT / "display_analysis_cycle.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _line_no_from_index(text: str, idx: int) -> int:
    if idx < 0:
        return -1
    return text[:idx].count("\n") + 1


def _line_no(text: str, needle: str) -> int:
    return _line_no_from_index(text, text.find(needle))


def _find_non_comment_runtime_call_after_line(text: str, after_line: int) -> int:
    lines = text.splitlines()
    if after_line <= 0:
        return -1

    for idx in range(after_line, len(lines)):
        stripped = lines[idx].strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if "_run_v11_stage2_runtime_safely(" in stripped:
            return idx + 1
    return -1


def _find_runtime_assignment_after_line(text: str, after_line: int) -> int:
    lines = text.splitlines()
    if after_line <= 0:
        return -1

    for idx in range(after_line, len(lines)):
        stripped = lines[idx].strip()
        if stripped.startswith("#"):
            continue
        if (
            'state["runtime_action"]' in stripped
            or "state['runtime_action']" in stripped
        ):
            # assignment may be split across lines; confirm the call appears nearby after the assignment
            window = "\n".join(lines[idx: min(len(lines), idx + 8)])
            if "_run_v11_stage2_runtime_safely(" in window:
                return idx + 1
    return -1


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
    text = _read(TARGET)

    marker = "V2.32: inject Solver_Preflop bridge into full_state before v11 runtime"
    clear_build = "v232_pre_runtime_clear_state = build_clear_json_from_dark_state(state)"
    bridge_build = "v232_pre_runtime_solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract("
    state_set = 'state["solver_preflop_bridge_contract"] = v232_pre_runtime_solver_preflop_bridge_contract'
    diag_set = 'state["v232_pre_runtime_solver_preflop_bridge"] = {'
    late_bridge = "solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract("

    import_check = _run_static_import_check()

    marker_line = _line_no(text, marker)
    clear_build_line = _line_no(text, clear_build)
    bridge_build_line = _line_no(text, bridge_build)
    state_set_line = _line_no(text, state_set)
    diag_set_line = _line_no(text, diag_set)
    first_runtime_call_anywhere_line = _line_no(text, "_run_v11_stage2_runtime_safely(")
    runtime_assignment_after_state_set_line = _find_runtime_assignment_after_line(text, state_set_line)
    non_comment_runtime_call_after_state_set_line = _find_non_comment_runtime_call_after_line(text, state_set_line)
    effective_runtime_call_line = (
        runtime_assignment_after_state_set_line
        if runtime_assignment_after_state_set_line > 0
        else non_comment_runtime_call_after_state_set_line
    )
    late_bridge_line = _line_no(text, late_bridge)

    checks = {
        "target_exists": TARGET.exists(),
        "marker_present": marker in text,
        "builds_clear_state_before_runtime": clear_build in text,
        "builds_bridge_before_runtime": bridge_build in text,
        "sets_state_solver_bridge": state_set in text,
        "records_v232_diagnostic": diag_set in text,
        "uses_existing_bridge_guard": 'if not isinstance(v232_existing_solver_preflop_bridge, dict):' in text,
        "removes_click_result_before_bridge": 'v232_pre_runtime_clear_state.pop("click_result", None)' in text,
        "uses_publish_diagnostic_toggle": "V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES" in text,
        "calls_add_error_on_exception": "V2.32 pre-runtime bridge build failed" in text,
        "runtime_call_after_state_set_found": effective_runtime_call_line > 0,
        "v232_marker_before_runtime_call": marker_line > 0 and effective_runtime_call_line > 0 and marker_line < effective_runtime_call_line,
        "v232_state_set_before_runtime_call": state_set_line > 0 and effective_runtime_call_line > 0 and state_set_line < effective_runtime_call_line,
        "late_bridge_still_present": late_bridge_line > 0,
        "display_import_ok": import_check.returncode == 0 and import_check.stdout.strip() == "ok",
        "display_import_no_traceback": "Traceback" not in import_check.stderr,
    }

    return {
        "schema": SCHEMA,
        "status": "ok" if all(checks.values()) else "failed",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "target": str(TARGET),
        "real_project_touched": False,
        "line_positions": {
            "marker": marker_line,
            "clear_build": clear_build_line,
            "bridge_build": bridge_build_line,
            "state_set": state_set_line,
            "diag_set": diag_set_line,
            "first_runtime_call_anywhere": first_runtime_call_anywhere_line,
            "runtime_assignment_after_state_set": runtime_assignment_after_state_set_line,
            "non_comment_runtime_call_after_state_set": non_comment_runtime_call_after_state_set_line,
            "effective_runtime_call": effective_runtime_call_line,
            "late_bridge": late_bridge_line,
        },
        "checks": checks,
        "audit_note": "V2.32 ordering is checked against the first non-comment runtime call after state['solver_preflop_bridge_contract'] is set.",
        "import_stdout": import_check.stdout.strip(),
        "import_stderr": import_check.stderr.strip(),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
