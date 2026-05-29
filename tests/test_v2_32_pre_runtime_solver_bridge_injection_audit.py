from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_32_pre_runtime_solver_bridge_injection_audit.py"


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


def test_v2_32_pre_runtime_solver_bridge_injection_audit() -> None:
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
    assert report["schema"] == "pokervision_solver_preflop_v232_pre_runtime_solver_bridge_injection_audit_v1"
    assert report["status"] == "ok"
    assert report["real_project_touched"] is False

    checks: dict[str, Any] = report["checks"]
    assert checks["target_exists"] is True
    assert checks["marker_present"] is True
    assert checks["builds_clear_state_before_runtime"] is True
    assert checks["builds_bridge_before_runtime"] is True
    assert checks["sets_state_solver_bridge"] is True
    assert checks["records_v232_diagnostic"] is True
    assert checks["uses_existing_bridge_guard"] is True
    assert checks["removes_click_result_before_bridge"] is True
    assert checks["uses_publish_diagnostic_toggle"] is True
    assert checks["calls_add_error_on_exception"] is True
    assert checks["runtime_call_after_state_set_found"] is True
    assert checks["v232_marker_before_runtime_call"] is True
    assert checks["v232_state_set_before_runtime_call"] is True
    assert checks["late_bridge_still_present"] is True
    assert checks["display_import_ok"] is True
    assert checks["display_import_no_traceback"] is True

    lines = report["line_positions"]
    assert lines["marker"] < lines["effective_runtime_call"]
    assert lines["state_set"] < lines["effective_runtime_call"]
