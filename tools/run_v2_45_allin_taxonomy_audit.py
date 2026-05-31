from __future__ import annotations

import json
import sys
from dataclasses import dataclass
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


@dataclass
class FakeSlot:
    x1: int = 100
    y1: int = 100
    x2: int = 900
    y2: int = 700

    @property
    def bbox(self) -> "FakeSlot":
        return self


def _button(cls: str, x: int) -> dict[str, Any]:
    return {"class_name": cls, "bbox_xyxy": [x, 520, x + 110, 570], "confidence": 0.99}


def _action_buttons(*classes: str) -> dict[str, Any]:
    best = {cls: _button(cls, 100 + i * 130) for i, cls in enumerate(classes)}
    return {"best_by_class": best, "detected_classes": list(classes)}


def _run_click(decision: dict[str, Any], buttons: dict[str, Any]) -> dict[str, Any]:
    old_dry = click_stub.V11_CLICK_DRY_RUN
    old_real = click_stub.V11_REAL_MOUSE_CLICK_ENABLED
    try:
        click_stub.V11_CLICK_DRY_RUN = True
        click_stub.V11_REAL_MOUSE_CLICK_ENABLED = False
        return build_and_maybe_execute_click_plan(
            solver_decision=decision,
            action_button_result=buttons,
            slot=FakeSlot(),
            active_confirmed=True,
        )
    finally:
        click_stub.V11_CLICK_DRY_RUN = old_dry
        click_stub.V11_REAL_MOUSE_CLICK_ENABLED = old_real


def _find_audit_exclusion(dark_state: dict[str, Any], case_id: str) -> str | None:
    audit = dark_state.get("player_participation_audit") or {}
    excluded = audit.get("excluded_from_clear_json") or []
    for item in excluded:
        if isinstance(item, dict):
            reason = item.get("exclude_reason")
            if reason:
                return str(reason)
    return None


def _player(clear_json: dict[str, Any], pos: str) -> dict[str, Any] | None:
    players = clear_json.get("players") or {}
    item = players.get(pos)
    return item if isinstance(item, dict) else None


def _cards_to_hand_class(cards):
    if not isinstance(cards, (list, tuple)) or len(cards) != 2:
        return ""
    ranks = []
    for card in cards:
        token = str(card or "").split("_", 1)[0].strip().upper()
        if token in {"ACE", "ACES"}:
            rank = "A"
        elif token in {"KING", "KINGS"}:
            rank = "K"
        elif token in {"QUEEN", "QUEENS"}:
            rank = "Q"
        else:
            rank = token[:1]
        ranks.append(rank)
    if len(ranks) == 2 and ranks[0] == ranks[1]:
        return ranks[0] + ranks[1]
    return "".join(ranks)


def _solver_decision_hand_class(decision):
    value = getattr(decision, "hero_hand_class", None)
    if value:
        return str(value)
    value = getattr(decision, "hand_class", None)
    if value:
        return str(value)
    return _cards_to_hand_class(getattr(decision, "hero_hand", None))


def _solver_runtime_decision(case_id: str, clear_json: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        d = solve_clear_json(clear_json)
    except Exception as exc:
        return None, str(exc)

    return {
        "status": "ok",
        "source": "PokerVision_Solver_Preflop",
        "decision_id": f"v245_{case_id}",
        "table_id": "table_01",
        "hand_id": "hand_v245",
        "frame_name": case_id,
        "action": d.engine_action if d.engine_action != "raise" else "bet_raise",
        "raw_action": d.raw_action,
        "engine_action": d.engine_action,
        "solver_raw_action": d.raw_action,
        "solver_engine_action": d.engine_action,
        "size_pct": d.size_pct,
        "hero_hand": list(d.hero_hand),
        "hand_class": _solver_decision_hand_class(d),
        "node_type": d.node_type,
        "safe_fallback_used": d.raw_action == "safe_fallback" or d.status == "fallback",
        "reason": d.reason,
        "source_frame_id": case_id,
        "click_sequence": list(d.click_sequence),
        "solver_fingerprint": d.solver_fingerprint,
    }, None


def _contains(errors: list[str], needle: str | None) -> bool:
    if not needle:
        return True
    joined = "\n".join(str(x) for x in errors)
    return needle in joined


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    category = str(case["category"])
    dark_state = json.loads(json.dumps(case["dark_state"]))
    expected = case.get("expected") or {}

    clear_json = build_clear_json_from_dark_state(dark_state)
    validation = validate_clear_json_contract(clear_json)
    validation_ok = bool(validation.get("ok"))

    result: dict[str, Any] = {
        "case_id": case_id,
        "category": category,
        "notes": case.get("notes") or [],
        "clear_json": clear_json,
        "validation": validation,
        "clear_validation_ok": validation_ok,
        "audit_exclusion_reason": _find_audit_exclusion(dark_state, case_id),
        "solver": None,
        "solver_error": None,
        "click_result": None,
        "checks": {},
    }

    solver_decision = None
    if validation_ok:
        solver_decision, solver_error = _solver_runtime_decision(case_id, clear_json)
        result["solver"] = solver_decision
        result["solver_error"] = solver_error
        if solver_decision is not None:
            result["click_result"] = _run_click(solver_decision, _action_buttons("FOLD", "Bet/Raise", "Call"))
    else:
        result["solver_error"] = "clear_validation_failed"

    checks: dict[str, bool] = {}

    if "clear_validation_ok" in expected:
        checks["clear_validation_ok"] = validation_ok is bool(expected["clear_validation_ok"])

    if "validation_error_contains" in expected:
        checks["validation_error_contains"] = _contains(list(validation.get("errors") or []), str(expected["validation_error_contains"]))

    if "solver_error_contains" in expected:
        checks["solver_error_contains"] = result["solver_error"] is not None and str(expected["solver_error_contains"]) in str(result["solver_error"])

    for key, pos in [
        ("clear_has_btn", "BTN"),
        ("clear_has_utg", "UTG"),
        ("clear_has_co", "CO"),
        ("clear_has_seat_04", "seat_04"),
    ]:
        if key in expected:
            checks[key] = (_player(clear_json, pos) is not None) is bool(expected[key])

    for key, pos in [
        ("clear_btn_chips", "BTN"),
        ("clear_utg_chips", "UTG"),
        ("clear_co_chips", "CO"),
    ]:
        if key in expected:
            player = _player(clear_json, pos) or {}
            checks[key] = player.get("chips") == expected[key]

    for key, pos in [
        ("clear_btn_all_in", "BTN"),
        ("clear_utg_all_in", "UTG"),
        ("clear_co_all_in", "CO"),
    ]:
        if key in expected:
            player = _player(clear_json, pos) or {}
            checks[key] = bool(player.get("all_in")) is bool(expected[key])

    for key, pos in [
        ("clear_btn_all_in_unknown_amount", "BTN"),
        ("clear_utg_all_in_unknown_amount", "UTG"),
        ("clear_co_all_in_unknown_amount", "CO"),
    ]:
        if key in expected:
            player = _player(clear_json, pos) or {}
            checks[key] = bool(player.get("all_in_unknown_amount")) is bool(expected[key])

    for key, pos in [
        ("clear_btn_stack", "BTN"),
        ("clear_utg_stack", "UTG"),
        ("clear_co_stack", "CO"),
    ]:
        if key in expected:
            player = _player(clear_json, pos) or {}
            checks[key] = player.get("stack") == expected[key]

    if "audit_exclusion_reason" in expected:
        checks["audit_exclusion_reason"] = result["audit_exclusion_reason"] == expected["audit_exclusion_reason"]

    if "solver_should_run" in expected:
        checks["solver_should_run"] = (result["solver"] is not None) is bool(expected["solver_should_run"])

    if "premium_guard_should_activate" in expected:
        click = result.get("click_result") or {}
        guard = click.get("premium_fold_guard") if isinstance(click, dict) else {}
        checks["premium_guard_should_activate"] = bool((guard or {}).get("active")) is bool(expected["premium_guard_should_activate"])

    if "expected_click_sequence" in expected:
        click = result.get("click_result") or {}
        checks["expected_click_sequence"] = list(click.get("target_sequence") or []) == list(expected["expected_click_sequence"])

    if "expected_node_type" in expected:
        solver = result.get("solver") or {}
        checks["expected_node_type"] = solver.get("node_type") == expected["expected_node_type"]

    if "expected_raw_action" in expected:
        solver = result.get("solver") or {}
        checks["expected_raw_action"] = solver.get("raw_action") == expected["expected_raw_action"]

    result["checks"] = checks
    result["ok"] = all(checks.values()) if checks else False
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_45_allin_taxonomy_audit.json")
    args = parser.parse_args()

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    results = [run_case(case) for case in payload["cases"]]

    report = {
        "schema": "v2_45_allin_taxonomy_audit_report_v1",
        "ok": all(r["ok"] for r in results),
        "cases_total": len(results),
        "cases_ok": sum(1 for r in results if r["ok"]),
        "cases_failed": sum(1 for r in results if not r["ok"]),
        "results": results,
    }

    print("V2.45 ALL-IN TAXONOMY AUDIT")
    print(f"cases_total={report['cases_total']} cases_ok={report['cases_ok']} cases_failed={report['cases_failed']}")
    print("-" * 130)
    for r in results:
        solver = r.get("solver") or {}
        click = r.get("click_result") or {}
        guard = (click.get("premium_fold_guard") or {}) if isinstance(click, dict) else {}
        print(
            f"{r['case_id']:52} {r['category']:46} "
            f"clear_ok={r['clear_validation_ok']} "
            f"solver_action={solver.get('raw_action')} "
            f"node={solver.get('node_type')} "
            f"click_seq={click.get('target_sequence')} "
            f"guard={guard.get('active')} "
            f"ok={r['ok']}"
        )
        if not r["ok"]:
            print(f"  checks={r['checks']}")
            print(f"  validation_errors={r['validation'].get('errors')}")
            print(f"  solver_error={r['solver_error']}")
    print("-" * 130)
    print(f"V2.45_ALLIN_TAXONOMY_AUDIT_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
