from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

for path in (PROJECT_ROOT, SNAPSHOT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from logic.clear_json_builder import build_clear_json_from_dark_state, validate_clear_json_contract

FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "v2_45_allin_taxonomy" / "cases.json"


def _player(clear_json: dict[str, Any], pos: str) -> dict[str, Any]:
    players = clear_json.get("players") or {}
    item = players.get(pos)
    return item if isinstance(item, dict) else {}


def _case_by_id(payload: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in payload["cases"]:
        if case.get("case_id") == case_id:
            return case
    raise KeyError(case_id)


def _build(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    clear_json = build_clear_json_from_dark_state(json.loads(json.dumps(case["dark_state"])))
    validation = validate_clear_json_contract(clear_json)
    return clear_json, validation


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_46_clear_json_allin_propagation_audit.json")
    args = parser.parse_args()

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    # Numeric all-in with normal numeric stack: must now propagate all_in.
    case = _case_by_id(payload, "allin_amount_detected_but_allin_flag_dropped")
    clear_json, validation = _build(case)
    btn = _player(clear_json, "BTN")
    checks["numeric_allin_propagates_flag"] = btn.get("all_in") is True
    checks["numeric_allin_keeps_chips"] = btn.get("chips") == 8.5
    checks["numeric_allin_validation_ok"] = validation.get("ok") is True
    details["numeric_allin"] = {"clear_json": clear_json, "validation": validation}

    # Numeric all-in with stack=None: V2.46 propagates flag but still leaves validation failure for V2.47.
    case = _case_by_id(payload, "allin_amount_detected_but_validation_rejected_stack_none")
    clear_json, validation = _build(case)
    btn = _player(clear_json, "BTN")
    checks["stack_none_allin_propagates_flag"] = btn.get("all_in") is True
    # V2.47 changed this from "still validation failed" to normalized/valid.
    checks["stack_none_allin_normalized_for_v247"] = (
        validation.get("ok") is True
        and btn.get("stack") == 0.0
        and btn.get("chips") == 23.5
    )
    details["stack_none_allin"] = {"clear_json": clear_json, "validation": validation}

    # Sitout all-in badge must not enter Clear_JSON as pressure.
    case = _case_by_id(payload, "sitout_false_positive_allin_badge")
    clear_json, validation = _build(case)
    checks["sitout_allin_excluded"] = "CO" not in (clear_json.get("players") or {})
    checks["sitout_allin_validation_ok"] = validation.get("ok") is True
    details["sitout_allin"] = {"clear_json": clear_json, "validation": validation}

    # Missing amount all-in stays non-propagated for V2.48 unknown-amount semantics.
    case = _case_by_id(payload, "allin_flag_no_amount_saved_as_active")
    clear_json, validation = _build(case)
    co = _player(clear_json, "CO")
    checks["missing_amount_allin_not_propagated_yet"] = co.get("all_in") is not True and co.get("chips") is False
    checks["missing_amount_allin_validation_ok"] = validation.get("ok") is True
    details["missing_amount_allin"] = {"clear_json": clear_json, "validation": validation}

    report = {
        "schema": "v2_46_clear_json_allin_propagation_audit_v1",
        "ok": all(checks.values()),
        "checks": checks,
        "details": details,
    }

    print("V2.46 CLEAR_JSON ALL-IN PROPAGATION AUDIT")
    for key, value in checks.items():
        print(f"{key:58} {value}")
    print("-" * 100)
    print(f"V2.46_CLEAR_JSON_ALLIN_PROPAGATION_AUDIT_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
