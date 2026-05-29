from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = "pokervision_solver_preflop_v228_live_transaction_gate_unlock_audit_v1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DISPLAY = SNAPSHOT_ROOT / "display_analysis_cycle.py"
GATE = SNAPSHOT_ROOT / "logic" / "table_action_transaction_gate.py"


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(SNAPSHOT_ROOT),
        text=True,
        capture_output=True,
        timeout=30,
    )


def build_report() -> dict[str, Any]:
    display_text = DISPLAY.read_text(encoding="utf-8", errors="replace") if DISPLAY.exists() else ""
    gate_text = GATE.read_text(encoding="utf-8", errors="replace") if GATE.exists() else ""

    marker = "V2.28: release early lifecycle lock if the frame cannot enter action runtime"
    release_reason = "v228_release_early_lifecycle_"
    anchor_after = "V2.0: the table transaction lifecycle starts before heavy analysis"

    marker_index = display_text.find(marker)
    anchor_index = display_text.find(anchor_after)

    gate_semantics_code = r"""
from logic.table_action_transaction_gate import TableActionTransactionGate

gate = TableActionTransactionGate(dry_run_counts_as_completed=False, release_on_inactive=True)

first = gate.begin_analysis_cycle(table_id="table_01")
blocked = gate.begin_analysis_cycle(table_id="table_01")
released = gate.abort_analysis_cycle(
    table_id="table_01",
    reason="v228_test_release_no_active_confirmed",
    message="test release",
)
second = gate.begin_analysis_cycle(table_id="table_01")

assert first.should_process is True, first
assert blocked.should_process is False, blocked
assert blocked.reason == "table_lifecycle_already_open_before_analysis", blocked
assert released["status"] == "aborted", released
assert second.should_process is True, second
print("ok")
"""
    gate_proc = _run_python(gate_semantics_code)

    checks = {
        "display_file_exists": DISPLAY.exists(),
        "gate_file_exists": GATE.exists(),
        "v228_marker_present": marker in display_text,
        "abort_analysis_cycle_used_in_display": ".abort_analysis_cycle(" in display_text,
        "v228_release_reason_present": release_reason in display_text,
        "release_block_before_v20_action_cycle_comment": marker_index != -1 and anchor_index != -1 and marker_index < anchor_index,
        "release_condition_requires_early_transaction": "early_action_transaction_decision is not None" in display_text,
        "release_condition_requires_no_action_runtime_candidate": "and not bool(action_runtime_candidate)" in display_text,
        "diagnostic_written_to_runtime_lifecycle": "early_lifecycle_release_before_action=early_lifecycle_release_before_action" in display_text,
        "gate_blocks_duplicate_open_lifecycle": "table_lifecycle_already_open_before_analysis" in gate_text,
        "gate_has_abort_analysis_cycle": "def abort_analysis_cycle" in gate_text,
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
