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

FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "v2_42_full_preflop_spot_matrix" / "cases.json"

FAKE_AVAILABLE_BUTTONS = {
    "FOLD", "Fold",
    "CALL", "Call",
    "Check", "Check/fold",
    "Raise", "Bet/Raise",
    "33%", "50%", "70%", "98%", "100%",
}

KNOWN_SEMANTIC_GAP_CASE_IDS: set[str] = set()


def _street(data: dict[str, Any]) -> str:
    board = data.get("board") if isinstance(data.get("board"), dict) else {}
    return str(data.get("street") or board.get("street") or "").lower()


def _has_click_result(data: dict[str, Any]) -> bool:
    return isinstance(data.get("click_result"), dict)


def _normalize_target_token(token: Any) -> str:
    text = str(token or "").strip()
    if text == "Raise":
        return "Bet/Raise"
    return text


def _fake_click(plan: dict[str, Any]) -> dict[str, Any]:
    seq = list(plan.get("target_sequence") or [])
    normalized = [_normalize_target_token(x) for x in seq]
    missing = [x for x in normalized if x not in FAKE_AVAILABLE_BUTTONS]

    if str(plan.get("status")) != "ok":
        return {
            "status": "blocked",
            "reason": "runtime_plan_not_ok",
            "action": plan.get("planned_action"),
            "target_sequence": seq,
            "missing": missing,
        }

    if missing:
        return {
            "status": "blocked",
            "reason": "fake_button_missing",
            "action": plan.get("planned_action"),
            "target_sequence": seq,
            "missing": missing,
        }

    return {
        "status": "clicked",
        "branch": "action_button",
        "action": plan.get("planned_action"),
        "target_sequence": seq,
        "guard_passed": True,
        "dry_run": True,
        "physical_click_executed": False,
    }


def _contains_any(value: str, expected: list[str]) -> bool:
    if not expected:
        return True
    return any(value == x or value.startswith(x) for x in expected)


def _legacy_action_decision_from_solver(decision: Any, runtime_decision: dict[str, Any] | None) -> dict[str, Any]:
    from logic.action_decision_stub import V06_ACTION_DECISION_SCHEMA_VERSION

    runtime_action = runtime_decision.get("action") if isinstance(runtime_decision, dict) else None
    engine_action = runtime_action or getattr(decision, "engine_action", None) or "fold"

    public_action = "raise" if engine_action == "bet_raise" else str(engine_action)
    if public_action not in {"fold", "call", "check", "check_fold", "bet", "raise"}:
        public_action = "fold"

    click_sequence = list(getattr(decision, "click_sequence", None) or [])
    target_buttons: list[str] = []
    size_policy = None

    for token in click_sequence:
        t = str(token)
        if t == "FOLD":
            target_buttons.append("FOLD")
        elif t == "CALL":
            target_buttons.append("Call")
        elif t == "Raise":
            target_buttons.append("Bet/Raise")
        elif t in {"33%", "50%", "70%", "98%", "100%"}:
            target_buttons.append(t)
            size_policy = {"type": "preset_pct", "value": t.rstrip("%"), "unit": "pct"}
        else:
            target_buttons.append(t)

    if not target_buttons:
        if public_action == "fold":
            target_buttons = ["FOLD"]
        elif public_action == "call":
            target_buttons = ["Call"]
        elif public_action == "check":
            target_buttons = ["Check"]
        elif public_action == "check_fold":
            target_buttons = ["Check", "Check/fold", "FOLD"]
        elif public_action in {"bet", "raise"}:
            target_buttons = ["Bet/Raise"]

    return {
        "schema_version": V06_ACTION_DECISION_SCHEMA_VERSION,
        "source": "Decision_JSON",
        "source_decision_frame_id": getattr(decision, "source_frame_id", None) or getattr(decision, "decision_id", None),
        "decision_id": getattr(decision, "decision_id", None),
        "status": "ok",
        "action": public_action,
        "size_policy": size_policy,
        "target_button_classes": target_buttons,
        "reason": getattr(decision, "reason", ""),
        "dry_run_safe": True,
        "solver_stub": True,
        "decision_context": {
            "street": "preflop",
            "source_frame_id": getattr(decision, "source_frame_id", None),
            "solver_preflop_runtime_source": True,
            "solver_source": "PokerVision_Solver_Preflop",
            "solver_status": getattr(decision, "status", None),
            "solver_raw_action": getattr(decision, "raw_action", None),
            "solver_engine_action": getattr(decision, "engine_action", None),
            "solver_action": engine_action,
            "solver_fingerprint": getattr(decision, "solver_fingerprint", None),
            "runtime_source_selection": "Solver_Preflop_Bridge",
            "spot": {
                "node_type": getattr(decision, "node_type", None),
            },
        },
    }


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    from solver_preflop.decision_engine import solve_clear_json
    from solver_preflop.pokervision_bridge import build_pokervision_bridge_payload
    from runtime.v11_stage1_runtime import _extract_solver_preflop_decision_from_state
    from logic.action_runtime_plan_builder import build_action_runtime_plan_from_action_decision

    case_id = str(case["case_id"])
    clear_json = dict(case["clear_json"])
    reject_reason = case.get("reject_reason")

    if reject_reason == "already_has_click_result":
        ok = _has_click_result(clear_json)
        return {
            "case_id": case_id,
            "label": case.get("label"),
            "kind": "reject",
            "ok": ok,
            "reject_reason": reject_reason,
            "actual_reject_reason": "already_has_click_result" if ok else "missing_click_result",
            "checks": {"reject_ok": ok},
        }

    if reject_reason == "not_preflop":
        actual = _street(clear_json)
        ok = actual != "preflop"
        return {
            "case_id": case_id,
            "label": case.get("label"),
            "kind": "reject",
            "ok": ok,
            "reject_reason": reject_reason,
            "actual_street": actual,
            "checks": {"reject_ok": ok},
        }

    decision = solve_clear_json(clear_json)
    bridge_payload = build_pokervision_bridge_payload(decision)

    full_state = {
        "solver_preflop_bridge_contract": {
            "status": bridge_payload.get("status"),
            "bridge_payload": bridge_payload,
            "raw_action": decision.raw_action,
            "engine_action": decision.engine_action,
            "click_sequence": list(decision.click_sequence),
            "decision_id": decision.decision_id,
            "solver_fingerprint": decision.solver_fingerprint,
            "source_frame_id": decision.source_frame_id,
        }
    }

    runtime_decision = _extract_solver_preflop_decision_from_state(
        full_state=full_state,
        solver_payload={"table_id": "table_01", "hand_id": case_id, "frame_name": case_id},
        solver_payload_path=Path(f"{case_id}.synthetic_solver_payload.json"),
    )

    plan_source_decision = _legacy_action_decision_from_solver(
        decision=decision,
        runtime_decision=runtime_decision if isinstance(runtime_decision, dict) else None,
    )
    plan = build_action_runtime_plan_from_action_decision(plan_source_decision)
    click_result = _fake_click(plan)

    expected_nodes = list(case.get("expected_node_any") or [])
    expected_actions = list(case.get("expected_raw_any") or [])

    node_ok = _contains_any(str(decision.node_type), expected_nodes)
    raw_ok = _contains_any(str(decision.raw_action), expected_actions)

    plan_ok = bool(plan.get("status") == "ok" and plan.get("target_sequence"))
    runtime_ok = isinstance(runtime_decision, dict) and bool(runtime_decision.get("action"))
    click_ok = click_result.get("status") == "clicked"
    final_ok = bool(click_ok and plan_ok and runtime_ok)

    checks = {
        "node_ok": node_ok,
        "raw_action_ok": raw_ok,
        "bridge_status_ok": bridge_payload.get("status") in {"ok", "fallback"},
        "runtime_decision_ok": runtime_ok,
        "runtime_plan_ok": plan_ok,
        "fake_click_ok": click_ok,
        "synthetic_final_ok": final_ok,
    }

    runtime_chain_ok = bool(
        checks["bridge_status_ok"]
        and checks["runtime_decision_ok"]
        and checks["runtime_plan_ok"]
        and checks["fake_click_ok"]
        and checks["synthetic_final_ok"]
    )
    semantic_exact_ok = bool(checks["node_ok"] and checks["raw_action_ok"])
    known_gap = bool((not semantic_exact_ok) and case_id in KNOWN_SEMANTIC_GAP_CASE_IDS)

    return {
        "case_id": case_id,
        "label": case.get("label"),
        "kind": "positive",
        "ok": runtime_chain_ok and (semantic_exact_ok or known_gap),
        "runtime_chain_ok": runtime_chain_ok,
        "semantic_exact_ok": semantic_exact_ok,
        "known_semantic_gap": known_gap,
        "checks": checks,
        "expected_node_any": expected_nodes,
        "actual_node_type": decision.node_type,
        "expected_raw_any": expected_actions,
        "actual_raw_action": decision.raw_action,
        "engine_action": decision.engine_action,
        "status": decision.status,
        "reason": decision.reason,
        "warnings": list(decision.warnings),
        "to_call_bb": decision.debug.get("to_call_bb"),
        "max_commitment_bb": decision.debug.get("max_commitment_bb"),
        "hero_commitment_bb": decision.debug.get("hero_commitment_bb"),
        "raise_levels": decision.debug.get("raise_levels"),
        "limpers": decision.debug.get("limpers"),
        "all_in_players": decision.debug.get("all_in_players"),
        "all_in_amount_bb": decision.debug.get("all_in_amount_bb"),
        "runtime_action": runtime_decision.get("action") if isinstance(runtime_decision, dict) else None,
        "runtime_raw_action": runtime_decision.get("raw_action") if isinstance(runtime_decision, dict) else None,
        "plan_status": plan.get("status"),
        "planned_action": plan.get("planned_action"),
        "target_sequence": plan.get("target_sequence"),
        "raise_branch_enabled": plan.get("raise_branch_enabled"),
        "click_result": click_result,
        "notes": list(case.get("notes") or []),
    }


def run_matrix() -> dict[str, Any]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    results = [_run_case(case) for case in payload["cases"]]

    positive = [r for r in results if r.get("kind") == "positive"]
    reject = [r for r in results if r.get("kind") == "reject"]

    runtime_failed = [r for r in positive if not r.get("runtime_chain_ok")]
    reject_failed = [r for r in reject if not r.get("ok")]
    semantic_failed = [r for r in positive if not r.get("semantic_exact_ok")]
    known_semantic_gaps = [r for r in semantic_failed if r.get("known_semantic_gap")]
    unexpected_semantic_failed = [r for r in semantic_failed if not r.get("known_semantic_gap")]

    runtime_chain_ok = not runtime_failed and not reject_failed
    semantic_exact_ok = not semantic_failed
    ok = runtime_chain_ok and not unexpected_semantic_failed

    return {
        "schema_version": "v2_42_full_preflop_spot_matrix_e2e_report_v2",
        "ok": ok,
        "runtime_chain_ok": runtime_chain_ok,
        "semantic_exact_ok": semantic_exact_ok,
        "cases_total": len(results),
        "cases_ok": sum(1 for r in results if r.get("ok")),
        "cases_failed": sum(1 for r in results if not r.get("ok")),
        "runtime_failed_total": len(runtime_failed),
        "runtime_failed_case_ids": [r["case_id"] for r in runtime_failed],
        "reject_failed_total": len(reject_failed),
        "reject_failed_case_ids": [r["case_id"] for r in reject_failed],
        "semantic_failed_total": len(semantic_failed),
        "known_semantic_gaps_total": len(known_semantic_gaps),
        "known_semantic_gap_case_ids": [r["case_id"] for r in known_semantic_gaps],
        "unexpected_semantic_failed_total": len(unexpected_semantic_failed),
        "unexpected_semantic_failed_case_ids": [r["case_id"] for r in unexpected_semantic_failed],
        "known_semantic_gap_registry": sorted(KNOWN_SEMANTIC_GAP_CASE_IDS),
        "results": results,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_42_full_preflop_spot_matrix_e2e.json")
    args = parser.parse_args()

    report = run_matrix()

    print("V2.42 FULL PREFLOP SPOT MATRIX E2E")
    print(
        f"cases_total={report['cases_total']} "
        f"cases_ok={report['cases_ok']} "
        f"cases_failed={report['cases_failed']}"
    )
    print(
        f"runtime_chain_ok={report['runtime_chain_ok']} "
        f"semantic_exact_ok={report['semantic_exact_ok']} "
        f"known_semantic_gaps={report['known_semantic_gaps_total']} "
        f"unexpected_semantic_failed={report['unexpected_semantic_failed_total']}"
    )
    print("-" * 150)
    print(f"{'CASE':45} {'LABEL':28} {'NODE':34} {'RAW':14} {'PLAN':10} {'SEQUENCE':24} {'OK'}")
    print("-" * 150)

    for r in report["results"]:
        if r.get("kind") == "reject":
            print(
                f"{r['case_id'][:45]:45} "
                f"{str(r.get('label'))[:28]:28} "
                f"{str(r.get('actual_reject_reason') or r.get('actual_street'))[:34]:34} "
                f"{'reject':14} {'skip':10} {'':24} {r.get('ok')}"
            )
        else:
            seq = " -> ".join(str(x) for x in (r.get("target_sequence") or []))
            print(
                f"{r['case_id'][:45]:45} "
                f"{str(r.get('label'))[:28]:28} "
                f"{str(r.get('actual_node_type'))[:34]:34} "
                f"{str(r.get('actual_raw_action'))[:14]:14} "
                f"{str(r.get('planned_action'))[:10]:10} "
                f"{seq[:24]:24} {r.get('ok')}"
            )
            if r.get("known_semantic_gap"):
                print("  KNOWN_SEMANTIC_GAP=True")
            if not r.get("ok"):
                print(f"  checks={r.get('checks')}")
                print(f"  expected_node_any={r.get('expected_node_any')} expected_raw_any={r.get('expected_raw_any')}")
                print(f"  reason={r.get('reason')}")
                print(f"  warnings={r.get('warnings')}")

    print("-" * 150)
    print(f"V2.42_FULL_PREFLOP_SPOT_MATRIX_E2E_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
