from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise AssertionError("No JSON object found in tool stdout")


def test_v2_28_live_transaction_gate_unlock_audit() -> None:
    project_root = _project_root()
    tool = project_root / "tools" / "run_v2_28_live_transaction_gate_unlock_audit.py"

    proc = subprocess.run(
        [sys.executable, str(tool)],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout + "\nSTDERR:\n" + proc.stderr

    payload = _extract_json_object(proc.stdout)
    assert payload["schema"] == "pokervision_solver_preflop_v228_live_transaction_gate_unlock_audit_v1"
    assert payload["status"] == "ok"
    assert payload["real_project_touched"] is False

    checks: dict[str, Any] = payload["checks"]
    assert checks["display_file_exists"] is True
    assert checks["gate_file_exists"] is True
    assert checks["v228_marker_present"] is True
    assert checks["abort_analysis_cycle_used_in_display"] is True
    assert checks["v228_release_reason_present"] is True
    assert checks["release_block_before_v20_action_cycle_comment"] is True
    assert checks["release_condition_requires_early_transaction"] is True
    assert checks["release_condition_requires_no_action_runtime_candidate"] is True
    assert checks["diagnostic_written_to_runtime_lifecycle"] is True
    assert checks["gate_blocks_duplicate_open_lifecycle"] is True
    assert checks["gate_has_abort_analysis_cycle"] is True
    assert checks["gate_semantics_ok"] is True
    assert checks["gate_semantics_no_traceback"] is True
