from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import sys

# V240_PROJECT_ROOT_SYSPATH: allow running this tool as python tools/...
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "v2_40_real_clear_json_adapter"
CASES_PATH = FIXTURE_ROOT / "cases.json"


def _load_cases() -> list[dict[str, Any]]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{CASES_PATH} must contain a list under 'cases'")
    return [dict(item) for item in cases]


def _load_fixture(case: dict[str, Any]) -> dict[str, Any]:
    fixture = str(case.get("fixture") or "")
    path = FIXTURE_ROOT / fixture
    if not path.exists():
        raise FileNotFoundError(f"Missing fixture for {case.get('case_id')}: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Fixture must be a JSON object: {path}")
    return data


def _approx_equal(a: Any, b: Any, tolerance: float = 1e-6) -> bool:
    try:
        return abs(float(a) - float(b)) <= tolerance
    except Exception:
        return False


def _run_positive_case(case: dict[str, Any]) -> dict[str, Any]:
    from solver_preflop.cards import hand_to_class
    from solver_preflop.clear_json_adapter import parse_clear_json_preflop
    from solver_preflop.decision_engine import solve_clear_json
    from solver_preflop.pokervision_bridge import build_pokervision_bridge_payload
    from solver_preflop.spot_classifier import classify_preflop_spot

    data = _load_fixture(case)
    frame = parse_clear_json_preflop(data)
    spot = classify_preflop_spot(frame)
    decision = solve_clear_json(data)
    bridge = build_pokervision_bridge_payload(decision)

    hand_class = hand_to_class(frame.hero_cards)
    bridge_action_decision = bridge.get("action_decision") if isinstance(bridge.get("action_decision"), dict) else {}
    runtime_hint = bridge.get("runtime_plan_candidate") if isinstance(bridge.get("runtime_plan_candidate"), dict) else {}

    checks = {
        "adapter_hero_ok": frame.hero_position == case.get("expected_hero_position"),
        "adapter_hand_ok": hand_class == case.get("expected_hand_class"),
        "node_type_ok": spot.node_type == case.get("expected_node_type"),
        "decision_status_ok": decision.status == case.get("expected_status"),
        "decision_action_ok": decision.raw_action == case.get("expected_action"),
        "to_call_ok": _approx_equal(spot.to_call_bb, case.get("expected_to_call_bb")),
        "no_solver_input_error_ok": decision.node_type != "solver_input_error",
        "no_safe_fallback_ok": decision.raw_action != "safe_fallback",
        "click_sequence_available_ok": bool(decision.click_sequence),
        "bridge_source_ok": bridge.get("source") == "PokerVision_Solver_Preflop",
        "bridge_action_decision_ok": bridge_action_decision.get("raw_action") == decision.raw_action,
        "bridge_runtime_hint_ok": runtime_hint.get("raw_action") == decision.raw_action,
    }

    ok = all(checks.values())

    return {
        "case_id": case.get("case_id"),
        "kind": "positive",
        "source_artifact_path": case.get("source_artifact_path"),
        "frame_id": frame.frame_id,
        "hero_position": frame.hero_position,
        "expected_hero_position": case.get("expected_hero_position"),
        "hero_cards": list(frame.hero_cards),
        "hand_class": hand_class,
        "expected_hand_class": case.get("expected_hand_class"),
        "node_type": spot.node_type,
        "expected_node_type": case.get("expected_node_type"),
        "raw_action": decision.raw_action,
        "expected_action": case.get("expected_action"),
        "status": decision.status,
        "expected_status": case.get("expected_status"),
        "to_call_bb": spot.to_call_bb,
        "expected_to_call_bb": case.get("expected_to_call_bb"),
        "max_commitment_bb": spot.max_commitment_bb,
        "hero_commitment_bb": spot.hero_commitment_bb,
        "range_source": decision.debug.get("range_source") if isinstance(decision.debug, dict) else None,
        "fallback_used": bool((decision.debug or {}).get("range_fallback_used")) if isinstance(decision.debug, dict) else None,
        "click_sequence": list(decision.click_sequence),
        "decision_id_present": bool(decision.decision_id),
        "bridge_action_decision_raw_action": bridge_action_decision.get("raw_action"),
        "bridge_runtime_hint_raw_action": runtime_hint.get("raw_action"),
        "checks": checks,
        "ok": ok,
    }


def _run_reject_case(case: dict[str, Any]) -> dict[str, Any]:
    from solver_preflop.clear_json_adapter import parse_clear_json_preflop
    from solver_preflop.decision_engine import solve_clear_json

    data = _load_fixture(case)
    error_message = ""
    adapter_rejected = False
    try:
        parse_clear_json_preflop(data)
    except Exception as exc:  # expected path
        adapter_rejected = True
        error_message = str(exc)

    decision = solve_clear_json(data)
    expected_error = str(case.get("expected_error_contains") or "")
    checks = {
        "adapter_rejected_ok": adapter_rejected,
        "error_contains_ok": expected_error.lower() in error_message.lower(),
        "solver_status_ok": decision.status == case.get("expected_solver_status"),
        "solver_node_type_ok": decision.node_type == case.get("expected_solver_node_type"),
        "solver_raw_action_ok": decision.raw_action == case.get("expected_solver_raw_action"),
        "solver_safe_sequence_ok": bool(decision.click_sequence),
    }
    ok = all(checks.values())

    return {
        "case_id": case.get("case_id"),
        "kind": "reject",
        "source_artifact_path": case.get("source_artifact_path"),
        "adapter_rejected": adapter_rejected,
        "adapter_error": error_message,
        "expected_error_contains": expected_error,
        "solver_status": decision.status,
        "solver_node_type": decision.node_type,
        "solver_raw_action": decision.raw_action,
        "solver_reason": decision.reason,
        "checks": checks,
        "ok": ok,
    }


def run_audit() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in _load_cases():
        kind = str(case.get("kind") or "positive")
        if kind == "positive":
            results.append(_run_positive_case(case))
        elif kind == "reject":
            results.append(_run_reject_case(case))
        else:
            results.append(
                {
                    "case_id": case.get("case_id"),
                    "kind": kind,
                    "ok": False,
                    "error": f"Unsupported case kind: {kind}",
                }
            )

    return {
        "schema_version": "v2_40_real_clear_json_adapter_audit_report_v1",
        "ok": all(bool(item.get("ok")) for item in results),
        "project_root": str(PROJECT_ROOT),
        "fixtures_root": str(FIXTURE_ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "results": results,
    }


def _print_summary(report: dict[str, Any]) -> None:
    print("V2.40 REAL CLEAR_JSON ADAPTER FIXTURE AUDIT")
    print(f"{'CASE':48} {'KIND':8} {'NODE/ERROR':34} {'ACTION':14} {'OK'}")
    print("-" * 122)
    for item in report.get("results", []):
        if item.get("kind") == "positive":
            node = str(item.get("node_type") or "")
            action = str(item.get("raw_action") or "")
        else:
            node = str(item.get("adapter_error") or "")[:34]
            action = str(item.get("solver_raw_action") or "")
        print(
            f"{str(item.get('case_id'))[:48]:48} "
            f"{str(item.get('kind'))[:8]:8} "
            f"{node[:34]:34} "
            f"{action[:14]:14} "
            f"{bool(item.get('ok'))}"
        )
        if not item.get("ok"):
            print(f"  checks: {item.get('checks')}")
    print("-" * 122)
    print(f"V2.40_REAL_CLEAR_JSON_ADAPTER_AUDIT_OK = {bool(report.get('ok'))}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="")
    args = parser.parse_args(argv)

    report = run_audit()
    _print_summary(report)

    if args.report_json:
        path = Path(args.report_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report_json={path}")

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
