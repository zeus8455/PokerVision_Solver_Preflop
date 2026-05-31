from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_46_clear_json_allin_propagation_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_46_clear_json_allin_propagation_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_46_clear_json_allin_propagation_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.46_CLEAR_JSON_ALLIN_PROPAGATION_AUDIT_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    checks = report["checks"]
    assert checks["numeric_allin_propagates_flag"] is True
    assert checks["numeric_allin_validation_ok"] is True
    assert checks["stack_none_allin_propagates_flag"] is True
    assert checks["stack_none_allin_normalized_for_v247"] is True
    assert checks["sitout_allin_excluded"] is True
    assert checks["missing_amount_allin_not_propagated_yet"] is True
