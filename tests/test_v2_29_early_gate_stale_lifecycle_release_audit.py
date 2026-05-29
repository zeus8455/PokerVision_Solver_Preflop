from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_29_early_gate_stale_lifecycle_release_audit.py"


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


def test_v2_29_early_gate_stale_lifecycle_release_audit() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr

    report = _extract_json_object(result.stdout)
    assert report["schema"] == "pokervision_solver_preflop_v229_early_gate_stale_lifecycle_release_audit_v1"
    assert report["status"] == "ok"
    assert report["real_project_touched"] is False

    checks: dict[str, Any] = report["checks"]
    assert checks["display_file_exists"] is True
    assert checks["gate_file_exists"] is True
    assert checks["v229_marker_present"] is True
    assert checks["v229_reason_present"] is True
    assert checks["v229_release_print_present"] is True
    assert checks["v229_before_v228_late_release"] is True
    assert checks["v229_order_inside_early_gate"] is True
    assert checks["release_condition_limited_to_early_lifecycle_reason"] is True
    assert checks["abort_analysis_cycle_used"] is True
    assert checks["continues_after_release"] is True
    assert checks["gate_has_abort_analysis_cycle"] is True
    assert checks["gate_blocks_duplicate_lifecycle"] is True
    assert checks["gate_semantics_ok"] is True
    assert checks["gate_semantics_no_traceback"] is True

    lines = report["line_positions"]
    assert lines["early_skip"] < lines["v229_marker"]
    assert lines["v229_marker"] < lines["v228_late_release_marker"]
