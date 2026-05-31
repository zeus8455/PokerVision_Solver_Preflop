from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_45_allin_taxonomy_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_45_allin_taxonomy_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_45_allin_taxonomy_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.45_ALLIN_TAXONOMY_AUDIT_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["cases_total"] == 7
    assert report["cases_failed"] == 0

    by_id = {case["case_id"]: case for case in report["results"]}
    kk_case = by_id["allin_flag_no_amount_saved_as_active"]
    assert kk_case["click_result"]["target_sequence"] == ["Bet/Raise"]
    assert kk_case["click_result"]["premium_fold_guard"]["active"] is True

    weak_categories = {case["category"] for case in report["results"]}
    assert "SITOUT_FALSE_POSITIVE_ALLIN_BADGE" in weak_categories
    assert ("ALLIN_AMOUNT_DETECTED_BUT_VALIDATION_REJECTED" in weak_categories or "ALLIN_AMOUNT_DETECTED_STACK_NONE_NORMALIZED" in weak_categories)
    # V2.46 changes this live category from flag dropped to flag propagated.
    assert (
        "ALLIN_AMOUNT_DETECTED_BUT_ALLIN_FLAG_DROPPED" in weak_categories
        or "ALLIN_AMOUNT_DETECTED_AND_FLAG_PROPAGATED" in weak_categories
    )
    assert ("ALLIN_FLAG_NO_AMOUNT_SAVED_AS_ACTIVE" in weak_categories or "ALLIN_UNKNOWN_AMOUNT_MARKED" in weak_categories)
    assert "ALLIN_FLAG_NO_AMOUNT_NO_CLEAR" in weak_categories
    assert "POSTFLOP_IGNORED" in weak_categories
