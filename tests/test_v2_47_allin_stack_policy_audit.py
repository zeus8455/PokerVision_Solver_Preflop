from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_47_allin_stack_policy_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_47_allin_stack_policy_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_47_allin_stack_policy_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.47_ALLIN_STACK_POLICY_AUDIT_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    checks = report["checks"]
    assert checks["clear_btn_stack_none_normalized_to_zero"] is True
    assert checks["clear_btn_validation_ok"] is True
    assert checks["clear_utg_stack_none_normalized_to_zero"] is True
    assert checks["clear_utg_validation_ok"] is True
    assert checks["solver_payload_btn_allin_true"] is True
    assert checks["solver_payload_btn_stack_zero"] is True
