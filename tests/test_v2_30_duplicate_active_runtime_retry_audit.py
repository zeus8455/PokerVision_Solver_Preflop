from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_30_duplicate_active_runtime_retry_audit.py"


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


def test_v2_30_duplicate_active_runtime_retry_audit() -> None:
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
    assert report["schema"] == "pokervision_solver_preflop_v230_duplicate_active_runtime_retry_audit_v1"
    assert report["status"] == "ok"
    assert report["real_project_touched"] is False

    checks: dict[str, Any] = report["checks"]
    assert checks["display_file_exists"] is True
    assert checks["replace_import_present"] is True
    assert checks["v230_marker_present"] is True
    assert checks["v230_retry_reason_present"] is True
    assert checks["v230_retry_log_present"] is True
    assert checks["checks_runtime_plan_dir"] is True
    assert checks["checks_final_clear_dir"] is True
    assert checks["requires_no_runtime_plan"] is True
    assert checks["requires_no_final_clear"] is True
    assert checks["limited_to_duplicate_active_blocked"] is True
    assert checks["uses_dataclass_replace"] is True
    assert checks["sets_should_process_true"] is True
    assert checks["sets_retry_event_id"] is True
    assert checks["v230_before_runtime_candidate"] is True
    assert checks["v230_before_duplicate_hard_stop"] is True
    assert checks["v230_after_duplicate_suppression_log"] is True
    assert checks["display_import_ok"] is True
    assert checks["display_import_no_traceback"] is True
