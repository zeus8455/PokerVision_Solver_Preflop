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

from config import CARD_HERO_SEAT_NAME
from logic.clear_json_builder import build_clear_json_from_dark_state, validate_clear_json_contract
from runtime.solver_payload_builder import build_solver_payload

FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "v2_45_allin_taxonomy" / "cases.json"


def _case_by_id(payload: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in payload["cases"]:
        if case.get("case_id") == case_id:
            return case
    raise KeyError(case_id)


def _player(clear_json: dict[str, Any], pos: str) -> dict[str, Any]:
    item = (clear_json.get("players") or {}).get(pos)
    return item if isinstance(item, dict) else {}


def _build_payload_fixture() -> dict[str, Any]:
    hero_seat = CARD_HERO_SEAT_NAME
    villain_seat = "Player_seat1" if hero_seat != "Player_seat1" else "Player_seat2"
    return {
        "table": {
            "frame_id": "v2_47_solver_payload_frame",
            "frame_name": "hand_v247_preflop_01",
            "table_id": "table_01",
            "hand_id": "hand_v247",
            "action_event_id": "event_v247",
        },
        "runtime_event": {
            "should_process": True,
            "action_event_id": "event_v247",
            "action_signature": "sig_v247",
        },
        "table_structure": {
            "classes": {
                "Board": {"street": "preflop", "cards": []},
                "Total_pot": {"value": 25.0},
            }
        },
        "players": {
            "seats": {
                villain_seat: {
                    "position": "BTN",
                    "fold": False,
                    "all_in": True,
                    "stack": {"detect": False, "value": None},
                    "chips": {"detect": True, "value": 23.5},
                },
                hero_seat: {
                    "position": "BB",
                    "fold": False,
                    "hero_cards": ["A_spades", "Q_spades"],
                    "stack": {"detect": True, "value": 99.0},
                    "chips": {"detect": True, "value": 1.0},
                },
            }
        },
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_47_allin_stack_policy_audit.json")
    args = parser.parse_args()

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    case = _case_by_id(payload, "allin_amount_detected_but_validation_rejected_stack_none")
    clear_json = build_clear_json_from_dark_state(json.loads(json.dumps(case["dark_state"])))
    validation = validate_clear_json_contract(clear_json)
    btn = _player(clear_json, "BTN")
    checks["clear_btn_stack_none_normalized_to_zero"] = btn.get("stack") == 0.0
    checks["clear_btn_allin_true"] = btn.get("all_in") is True
    checks["clear_btn_chips_numeric"] = btn.get("chips") == 23.5
    checks["clear_btn_validation_ok"] = validation.get("ok") is True
    details["clear_btn_case"] = {"clear_json": clear_json, "validation": validation}

    case = _case_by_id(payload, "allin_amount_pending_only_no_final")
    clear_json = build_clear_json_from_dark_state(json.loads(json.dumps(case["dark_state"])))
    validation = validate_clear_json_contract(clear_json)
    utg = _player(clear_json, "UTG")
    checks["clear_utg_stack_none_normalized_to_zero"] = utg.get("stack") == 0.0
    checks["clear_utg_allin_true"] = utg.get("all_in") is True
    checks["clear_utg_chips_numeric"] = utg.get("chips") == 21.0
    checks["clear_utg_validation_ok"] = validation.get("ok") is True
    details["clear_utg_case"] = {"clear_json": clear_json, "validation": validation}

    full_state = _build_payload_fixture()
    solver_payload = build_solver_payload(full_state)
    btn_payload = solver_payload["players"].get("BTN") or {}
    checks["solver_payload_btn_allin_true"] = btn_payload.get("all_in") is True
    checks["solver_payload_btn_stack_zero"] = btn_payload.get("stack") == 0.0
    checks["solver_payload_btn_chips_numeric"] = btn_payload.get("chips") == 23.5
    details["solver_payload"] = solver_payload

    report = {
        "schema": "v2_47_allin_stack_policy_audit_v1",
        "ok": all(checks.values()),
        "checks": checks,
        "details": details,
    }

    print("V2.47 ALL-IN STACK POLICY AUDIT")
    for key, value in checks.items():
        print(f"{key:58} {value}")
    print("-" * 100)
    print(f"V2.47_ALLIN_STACK_POLICY_AUDIT_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
