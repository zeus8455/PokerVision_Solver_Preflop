from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_49_dark_clear_solver_runtime_chain_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_49_dark_clear_solver_runtime_chain.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_49_dark_clear_solver_runtime_chain.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.49_DARK_CLEAR_SOLVER_RUNTIME_CHAIN_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    checks = report["checks"]

    assert checks["kk_unknown_allin_marker"] is True
    assert checks["kk_unknown_solver_node"] is True
    assert checks["kk_unknown_no_fold"] is True
    assert checks["weak_unknown_folds"] is True
    assert checks["numeric_allin_validation_ok"] is True
    assert checks["sitout_co_excluded"] is True
    assert checks["already_clicked_solver_input_error"] is True
    assert checks["premium_only_fold_blocked"] is True
