from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_42_full_preflop_spot_matrix_e2e_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_42_full_preflop_spot_matrix_e2e.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_42_full_preflop_spot_matrix_e2e.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.42_FULL_PREFLOP_SPOT_MATRIX_E2E_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["cases_total"] >= 45
    assert report["runtime_chain_ok"] is True
    assert report["runtime_failed_total"] == 0
    assert report["reject_failed_total"] == 0
    assert report["unexpected_semantic_failed_total"] == 0

    # V2.43 closes the V2.42 known semantic gaps.
    assert report["semantic_exact_ok"] is True
    assert report["known_semantic_gaps_total"] == 0
    assert report["semantic_failed_total"] == 0
