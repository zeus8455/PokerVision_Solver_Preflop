from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_31_accept_solver_preflop_fallback_contract_audit.py"


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


def test_v2_31_accept_solver_preflop_fallback_contract_audit() -> None:
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
    assert report["schema"] == "pokervision_solver_preflop_v231_accept_solver_preflop_fallback_contract_audit_v1"
    assert report["status"] == "ok"
    assert report["real_project_touched"] is False

    checks: dict[str, Any] = report["checks"]
    assert checks["target_exists"] is True
    assert checks["marker_present"] is True
    assert checks["old_strict_ok_check_removed"] is True
    assert checks["accepted_status_set_present"] is True
    assert checks["fallback_decision_returned"] is True
    assert checks["fallback_decision_status_ok"] is True
    assert checks["fallback_decision_source_solver_preflop"] is True
    assert checks["fallback_decision_id_not_stub"] is True
    assert checks["fallback_decision_action_fold"] is True
    assert checks["fallback_runtime_selection_bridge"] is True
    assert checks["ok_decision_still_returned"] is True
    assert checks["bad_status_still_rejected"] is True
