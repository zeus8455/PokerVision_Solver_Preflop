from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_43_allin_semantic_cleanup_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_43_allin_semantic_cleanup_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_43_allin_semantic_cleanup_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.43_ALLIN_SEMANTIC_CLEANUP_AUDIT_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["matrix_summary"]["runtime_chain_ok"] is True
    assert report["matrix_summary"]["semantic_exact_ok"] is True
    assert report["matrix_summary"]["known_semantic_gaps_total"] == 0
    assert report["matrix_summary"]["unexpected_semantic_failed_total"] == 0
