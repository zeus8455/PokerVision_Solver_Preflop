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


def _load_cases() -> dict[str, dict[str, Any]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {str(case["case_id"]): case for case in payload["cases"]}


def _deepcopy_json(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _button(cls: str, x: int) -> dict[str, Any]:
    return {"class_name": cls, "bbox_xyxy": [x, 520, x + 110, 570], "confidence": 0.99}


def _buttons(*classes: str) -> dict[str, Any]:
    return {"best_by_class": {cls: _button(cls, 100 + i * 130) for i, cls in enumerate(classes)}}


def _hand_class(cards: list[Any]) -> str:
    ranks = [str(c).split("_", 1)[0][0].upper() for c in cards]
    if len(ranks) == 2 and ranks[0] == ranks[1]:
        return ranks[0] + ranks[1]
    return "".join(ranks)


def _runtime_decision(decision: Any, case_id: str, clear_json: dict[str, Any]) -> dict[str, Any]:
    cards = list(getattr(decision, "hero_hand", []) or [])
    return {
        "status": getattr(decision, "status", "ok"),
        "source": "PokerVision_Solver_Preflop",
        "decision_id": f"v249_{case_id}",
        "table_id": str(clear_json.get("table_id") or "table_01"),
        "hand_id": str(clear_json.get("hand_id") or f"hand_v249_{case_id}"),
        "frame_name": case_id,
        "action": getattr(decision, "engine_action", None),
        "raw_action": getattr(decision, "raw_action", None),
        "engine_action": getattr(decision, "engine_action", None),
        "solver_raw_action": getattr(decision, "raw_action", None),
        "solver_engine_action": getattr(decision, "engine_action", None),
        "size_pct": getattr(decision, "size_pct", None),
        "hero_hand": cards,
        "hand_class": getattr(decision, "hand_class", None) or _hand_class(cards),
        "node_type": getattr(decision, "node_type", None),
        "safe_fallback_used": getattr(decision, "raw_action", None) == "safe_fallback" or getattr(decision, "status", None) == "fallback",
        "reason": getattr(decision, "reason", ""),
        "source_frame_id": case_id,
        "click_sequence": list(getattr(decision, "click_sequence", []) or []),
        "solver_fingerprint": getattr(decision, "solver_fingerprint", f"v249_{case_id}"),
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


def _build_clear_from_case(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    clear_json = build_clear_json_from_dark_state(_deepcopy_json(case["dark_state"]))
    validation = validate_clear_json_contract(clear_json)
    return clear_json, validation


def _solve_and_click(case_id: str, clear_json: dict[str, Any], buttons: dict[str, Any]) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    decision = solve_clear_json(clear_json)
    runtime_decision = _runtime_decision(decision, case_id, clear_json)
    click_result = _run_click(runtime_decision, buttons)
    return decision, runtime_decision, click_result


def _player(clear_json: dict[str, Any], pos: str) -> dict[str, Any]:
    player = (clear_json.get("players") or {}).get(pos)
    return player if isinstance(player, dict) else {}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_49_dark_clear_solver_runtime_chain.json")
    args = parser.parse_args()

    cases = _load_cases()
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    # Case 1: KK + opponent all_in=true + chips=false => unknown amount marker,
    # facing_allin_unknown_amount, safe_fallback, premium guard redirects away from FOLD.
    case_id = "kk_unknown_amount_allin_guard"
    base = _deepcopy_json(cases["allin_flag_no_amount_saved_as_active"])
    clear_json, validation = _build_clear_from_case(base)
    decision, runtime_decision, click_result = _solve_and_click(case_id, clear_json, _buttons("FOLD", "Bet/Raise", "Call"))
    co = _player(clear_json, "CO")
    checks["kk_unknown_clear_validation_ok"] = validation.get("ok") is True
    checks["kk_unknown_allin_marker"] = co.get("all_in_unknown_amount") is True
    checks["kk_unknown_solver_node"] = decision.node_type == "facing_allin_unknown_amount"
    checks["kk_unknown_solver_safe_fallback"] = decision.raw_action == "safe_fallback"
    checks["kk_unknown_guard_active"] = bool((click_result.get("premium_fold_guard") or {}).get("active")) is True
    checks["kk_unknown_no_fold"] = "FOLD" not in list(click_result.get("target_sequence") or [])
    checks["kk_unknown_raise_or_call"] = list(click_result.get("target_sequence") or []) in (["Bet/Raise"], ["Raise"], ["Call"])
    details[case_id] = {"clear_json": clear_json, "validation": validation, "decision": runtime_decision, "click_result": click_result}

    # Case 2: weak 72o + same unknown amount all-in => still FOLD, guard inactive.
    case_id = "weak_unknown_amount_allin_folds"
    weak = _deepcopy_json(cases["allin_flag_no_amount_saved_as_active"])
    weak["dark_state"]["players"]["SB"]["cards"] = ["7_clubs", "2_diamonds"]
    clear_json, validation = _build_clear_from_case(weak)
    decision, runtime_decision, click_result = _solve_and_click(case_id, clear_json, _buttons("FOLD", "Bet/Raise", "Call"))
    checks["weak_unknown_clear_validation_ok"] = validation.get("ok") is True
    checks["weak_unknown_solver_node"] = decision.node_type == "facing_allin_unknown_amount"
    checks["weak_unknown_guard_inactive"] = bool((click_result.get("premium_fold_guard") or {}).get("active")) is False
    checks["weak_unknown_folds"] = list(click_result.get("target_sequence") or []) == ["FOLD"]
    details[case_id] = {"clear_json": clear_json, "validation": validation, "decision": runtime_decision, "click_result": click_result}

    # Case 3: numeric all-in + stack=None => valid Clear_JSON, stack=0.0, all_in=true.
    case_id = "numeric_allin_stack_none_valid"
    clear_json, validation = _build_clear_from_case(cases["allin_amount_detected_but_validation_rejected_stack_none"])
    btn = _player(clear_json, "BTN")
    decision, runtime_decision, click_result = _solve_and_click(case_id, clear_json, _buttons("FOLD", "Bet/Raise", "Call"))
    checks["numeric_allin_validation_ok"] = validation.get("ok") is True
    checks["numeric_allin_btn_allin_true"] = btn.get("all_in") is True
    checks["numeric_allin_btn_stack_zero"] = btn.get("stack") == 0.0
    checks["numeric_allin_btn_chips_numeric"] = btn.get("chips") == 23.5
    checks["numeric_allin_solver_is_allin_or_fallback"] = (
        "allin" in str(decision.node_type).lower()
        or "all_in" in str(decision.node_type).lower()
        or decision.raw_action == "safe_fallback"
    )
    details[case_id] = {"clear_json": clear_json, "validation": validation, "decision": runtime_decision, "click_result": click_result}

    # Case 4: sitout all-in false-positive should not create all-in pressure.
    case_id = "sitout_allin_excluded"
    clear_json, validation = _build_clear_from_case(cases["sitout_false_positive_allin_badge"])
    decision, runtime_decision, click_result = _solve_and_click(case_id, clear_json, _buttons("FOLD", "Check", "Check/fold"))
    players = clear_json.get("players") or {}
    checks["sitout_validation_ok"] = validation.get("ok") is True
    checks["sitout_co_excluded"] = "CO" not in players
    checks["sitout_no_allin_marker_remaining"] = all(
        not bool((player or {}).get("all_in")) and not bool((player or {}).get("all_in_unknown_amount"))
        for player in players.values()
        if isinstance(player, dict)
    )
    details[case_id] = {"clear_json": clear_json, "validation": validation, "decision": runtime_decision, "click_result": click_result}

    # Case 5: already-clicked Clear_JSON must reject through solver_input_error/safe_fallback path.
    case_id = "already_clicked_clear_json_rejects"
    clear_json, validation = _build_clear_from_case(cases["allin_amount_detected_but_allin_flag_dropped"])
    clear_json["click_result"] = {"completed": True, "target_sequence": ["FOLD"], "source": "v249_fixture"}
    decision, runtime_decision, click_result = _solve_and_click(case_id, clear_json, _buttons("FOLD", "Bet/Raise", "Call"))
    checks["already_clicked_solver_input_error"] = decision.node_type == "solver_input_error"
    checks["already_clicked_safe_fallback"] = decision.raw_action == "safe_fallback"
    checks["already_clicked_fold_path"] = list(click_result.get("target_sequence") or []) == ["FOLD"]
    details[case_id] = {"clear_json": clear_json, "validation": validation, "decision": runtime_decision, "click_result": click_result}

    # Case 6: premium fallback with only FOLD visible must block instead of clicking FOLD.
    case_id = "premium_only_fold_visible_blocks"
    base = _deepcopy_json(cases["allin_flag_no_amount_saved_as_active"])
    clear_json, validation = _build_clear_from_case(base)
    decision, runtime_decision, click_result = _solve_and_click(case_id, clear_json, _buttons("FOLD"))
    checks["premium_only_fold_guard_active"] = bool((click_result.get("premium_fold_guard") or {}).get("active")) is True
    checks["premium_only_fold_blocked"] = str(click_result.get("status")).lower() == "blocked" or list(click_result.get("target_sequence") or []) == []
    checks["premium_only_fold_no_fold_click"] = "FOLD" not in list(click_result.get("target_sequence") or [])
    details[case_id] = {"clear_json": clear_json, "validation": validation, "decision": runtime_decision, "click_result": click_result}

    report = {
        "schema": "v2_49_dark_clear_solver_runtime_chain_v1",
        "ok": all(checks.values()),
        "checks": checks,
        "details": details,
    }

    print("V2.49 DARK->CLEAR->SOLVER->RUNTIME CHAIN")
    for key, value in checks.items():
        print(f"{key:64} {value}")
    print("-" * 110)
    print(f"V2.49_DARK_CLEAR_SOLVER_RUNTIME_CHAIN_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
