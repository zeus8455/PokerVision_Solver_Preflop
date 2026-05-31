from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_48_unknown_amount_allin_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_48_unknown_amount_allin_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_48_unknown_amount_allin_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.48_UNKNOWN_AMOUNT_ALLIN_AUDIT_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    checks = report["checks"]
    assert checks["clear_co_allin_unknown_amount_true"] is True
    assert checks["solver_node_facing_unknown_allin"] is True
    assert checks["premium_guard_sequence_bet_raise"] is True
    assert checks["weak_safe_fallback_fold"] is True
