from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_41_safe_fallback_runtime_fold_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_41_safe_fallback_runtime_fold_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_41_safe_fallback_runtime_fold_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )
    assert "V2.41_SAFE_FALLBACK_RUNTIME_FOLD_AUDIT_OK = True" in completed.stdout
    assert report_path.exists()
