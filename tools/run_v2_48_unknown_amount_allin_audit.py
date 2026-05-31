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
from solver_preflop.decision_engine import solve_clear_json
import runtime.action_click_stub as click_stub
from runtime.action_click_stub import build_and_maybe_execute_click_plan

FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "v2_45_allin_taxonomy" / "cases.json"


class FakeSlot:
    x1 = 100
    y1 = 100
    x2 = 900
    y2 = 700

    @property
    def bbox(self):
        return self


def _button(cls: str, x: int) -> dict[str, Any]:
    return {"class_name": cls, "bbox_xyxy": [x, 520, x + 110, 570], "confidence": 0.99}


def _buttons(*classes: str) -> dict[str, Any]:
    return {"best_by_class": {cls: _button(cls, 100 + i * 130) for i, cls in enumerate(classes)}}


def _case(case_id: str) -> dict[str, Any]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for c in payload["cases"]:
        if c["case_id"] == case_id:
            return c
    raise KeyError(case_id)


def _hand_class(cards: list[Any]) -> str:
    ranks = [str(c).split("_", 1)[0][0].upper() for c in cards]
    if len(ranks) == 2 and ranks[0] == ranks[1]:
        return ranks[0] + ranks[1]
    return "".join(ranks)


def _runtime_decision(decision: Any, case_id: str) -> dict[str, Any]:
    cards = list(decision.hero_hand)
    return {
        "status": "ok",
        "source": "PokerVision_Solver_Preflop",
        "decision_id": f"v248_{case_id}",
        "table_id": "table_01",
        "hand_id": "hand_v248",
        "frame_name": case_id,
        "action": decision.engine_action,
        "raw_action": decision.raw_action,
        "engine_action": decision.engine_action,
        "solver_raw_action": decision.raw_action,
        "solver_engine_action": decision.engine_action,
        "size_pct": decision.size_pct,
        "hero_hand": cards,
        "hand_class": _hand_class(cards),
        "node_type": decision.node_type,
        "safe_fallback_used": decision.raw_action == "safe_fallback" or decision.status == "fallback",
        "reason": decision.reason,
        "source_frame_id": case_id,
        "click_sequence": list(decision.click_sequence),
        "solver_fingerprint": decision.solver_fingerprint,
    }


def _run_click(runtime_decision: dict[str, Any], buttons: dict[str, Any]) -> dict[str, Any]:
    old_dry = click_stub.V11_CLICK_DRY_RUN
    old_real = click_stub.V11_REAL_MOUSE_CLICK_ENABLED
    try:
        click_stub.V11_CLICK_DRY_RUN = True
        click_stub.V11_REAL_MOUSE_CLICK_ENABLED = False
        return build_and_maybe_execute_click_plan(
            solver_decision=runtime_decision,
            action_button_result=buttons,
            slot=FakeSlot(),
            active_confirmed=True,
        )
    finally:
        click_stub.V11_CLICK_DRY_RUN = old_dry
        click_stub.V11_REAL_MOUSE_CLICK_ENABLED = old_real


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_48_unknown_amount_allin_audit.json")
    args = parser.parse_args()

    checks: dict[str, bool] = {}
    case = _case("allin_flag_no_amount_saved_as_active")
    clear_json = build_clear_json_from_dark_state(json.loads(json.dumps(case["dark_state"])))
    validation = validate_clear_json_contract(clear_json)
    co = (clear_json.get("players") or {}).get("CO") or {}
    decision = solve_clear_json(clear_json)
    runtime_decision = _runtime_decision(decision, case["case_id"])
    click = _run_click(runtime_decision, _buttons("FOLD", "Bet/Raise", "Call"))

    checks["clear_co_allin_unknown_amount_true"] = co.get("all_in_unknown_amount") is True
    checks["clear_validation_ok"] = validation.get("ok") is True
    checks["solver_node_facing_unknown_allin"] = decision.node_type == "facing_allin_unknown_amount"
    checks["solver_raw_safe_fallback"] = decision.raw_action == "safe_fallback"
    checks["premium_guard_active_for_kk"] = bool((click.get("premium_fold_guard") or {}).get("active")) is True
    checks["premium_guard_sequence_bet_raise"] = click.get("target_sequence") == ["Bet/Raise"]
    checks["premium_guard_no_fold"] = "FOLD" not in list(click.get("target_sequence") or [])

    weak_case = json.loads(json.dumps(case))
    weak_case["case_id"] = "weak_unknown_amount_allin_72o"
    weak_case["dark_state"]["players"]["SB"]["cards"] = ["7_clubs", "2_diamonds"]
    weak_clear = build_clear_json_from_dark_state(weak_case["dark_state"])
    weak_decision = solve_clear_json(weak_clear)
    weak_runtime = _runtime_decision(weak_decision, weak_case["case_id"])
    weak_click = _run_click(weak_runtime, _buttons("FOLD", "Bet/Raise", "Call"))
    checks["weak_node_facing_unknown_allin"] = weak_decision.node_type == "facing_allin_unknown_amount"
    checks["weak_safe_fallback_fold"] = weak_click.get("target_sequence") == ["FOLD"]
    checks["weak_guard_inactive"] = bool((weak_click.get("premium_fold_guard") or {}).get("active")) is False

    report = {
        "schema": "v2_48_unknown_amount_allin_audit_v1",
        "ok": all(checks.values()),
        "checks": checks,
        "details": {
            "clear_json": clear_json,
            "validation": validation,
            "decision": {
                "node_type": decision.node_type,
                "raw_action": decision.raw_action,
                "engine_action": decision.engine_action,
                "reason": decision.reason,
                "hero_hand": list(decision.hero_hand),
            },
            "click": click,
            "weak_decision": {
                "node_type": weak_decision.node_type,
                "raw_action": weak_decision.raw_action,
                "engine_action": weak_decision.engine_action,
                "reason": weak_decision.reason,
                "hero_hand": list(weak_decision.hero_hand),
            },
            "weak_click": weak_click,
        },
    }

    print("V2.48 UNKNOWN-AMOUNT ALL-IN AUDIT")
    for k, v in checks.items():
        print(f"{k:58} {v}")
    print("-" * 100)
    print(f"V2.48_UNKNOWN_AMOUNT_ALLIN_AUDIT_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
