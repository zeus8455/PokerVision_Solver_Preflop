from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = "pokervision_solver_preflop_v229_early_gate_stale_lifecycle_release_audit_v1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DISPLAY = SNAPSHOT_ROOT / "display_analysis_cycle.py"
GATE = SNAPSHOT_ROOT / "logic" / "table_action_transaction_gate.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _line_no(text: str, needle: str) -> int:
    idx = text.find(needle)
    if idx < 0:
        return -1
    return text[:idx].count("\n") + 1


def _window_after(text: str, needle: str, chars: int = 5000) -> str:
    idx = text.find(needle)
    if idx < 0:
        return ""
    return text[idx : idx + chars]


def _run_gate_semantics() -> subprocess.CompletedProcess[str]:
    code = r"""
from logic.table_action_transaction_gate import TableActionTransactionGate

gate = TableActionTransactionGate(dry_run_counts_as_completed=False, release_on_inactive=True)

first = gate.begin_analysis_cycle(table_id="table_03")
blocked = gate.begin_analysis_cycle(table_id="table_03")
released = gate.abort_analysis_cycle(
    table_id="table_03",
    reason="v229_release_stale_lifecycle_before_heavy_analysis",
    message="test release before continue",
)
second = gate.begin_analysis_cycle(table_id="table_03")

assert first.should_process is True, first
assert blocked.should_process is False, blocked
assert blocked.reason == "table_lifecycle_already_open_before_analysis", blocked
assert released["status"] == "aborted", released
assert released["reason"] == "v229_release_stale_lifecycle_before_heavy_analysis", released
assert second.should_process is True, second
print("ok")
"""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(SNAPSHOT_ROOT),
        text=True,
        capture_output=True,
        timeout=30,
    )


def build_report() -> dict[str, Any]:
    display = _read(DISPLAY)
    gate = _read(GATE)

    early_skip = "heavy analysis skipped by early lifecycle gate"
    marker = "V2.29: release stale early lifecycle directly inside the early gate blocked path"
    release_print = "V2.29 released stale early lifecycle before continue"
    reason = "v229_release_stale_lifecycle_before_heavy_analysis"
    v228_marker = "V2.28: release early lifecycle lock if the frame cannot enter action runtime"

    line_early_skip = _line_no(display, early_skip)
    line_marker = _line_no(display, marker)
    line_reason = _line_no(display, reason)
    line_release_print = _line_no(display, release_print)
    line_v228_marker = _line_no(display, v228_marker)

    v229_window = _window_after(display, marker, chars=5000)

    order_ok = (
        line_early_skip > 0
        and line_marker > line_early_skip
        and line_reason >= line_marker
        and (line_v228_marker == -1 or line_marker < line_v228_marker)
    )

    continues_after_release = (
        "current frame remains skipped" in v229_window
        and "\n                continue\n" in v229_window
    )

    gate_proc = _run_gate_semantics()

    checks = {
        "display_file_exists": DISPLAY.exists(),
        "gate_file_exists": GATE.exists(),
        "v229_marker_present": marker in display,
        "v229_reason_present": reason in display,
        "v229_release_print_present": release_print in display,
        "v229_before_v228_late_release": line_v228_marker == -1 or (0 < line_marker < line_v228_marker),
        "v229_order_inside_early_gate": order_ok,
        "release_condition_limited_to_early_lifecycle_reason": 'str(early_action_transaction_decision.reason) == "table_lifecycle_already_open_before_analysis"' in display,
        "abort_analysis_cycle_used": ".abort_analysis_cycle(" in display,
        "continues_after_release": continues_after_release,
        "gate_has_abort_analysis_cycle": "def abort_analysis_cycle" in gate,
        "gate_blocks_duplicate_lifecycle": "table_lifecycle_already_open_before_analysis" in gate,
        "gate_semantics_ok": gate_proc.returncode == 0 and gate_proc.stdout.strip() == "ok",
        "gate_semantics_no_traceback": "Traceback" not in gate_proc.stderr,
    }

    return {
        "schema": SCHEMA,
        "status": "ok" if all(checks.values()) else "failed",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "display_analysis_cycle": str(DISPLAY),
        "table_action_transaction_gate": str(GATE),
        "real_project_touched": False,
        "line_positions": {
            "early_skip": line_early_skip,
            "v229_marker": line_marker,
            "v229_reason": line_reason,
            "v229_release_print": line_release_print,
            "v228_late_release_marker": line_v228_marker,
        },
        "checks": checks,
        "gate_semantics_stdout": gate_proc.stdout.strip(),
        "gate_semantics_stderr": gate_proc.stderr.strip(),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
