from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
FIXTURE = ROOT / "tests" / "fixtures" / "v2_35_synthetic_click_gate" / "cases.json"


def _configure_live_env() -> None:
    os.environ["POKERVISION_CONTROLLED_LIVE_READY_PROFILE"] = "V8_1_CONTROLLED_ACTION_BUTTON"
    os.environ["POKERVISION_CONTROLLED_LIVE_TEST_SCOPE"] = "V8_7_FULL_LIVE_CHAIN_NO_LIMIT"
    os.environ["POKERVISION_CONTROLLED_LIVE_CLICK"] = "V3_1_ONE_CLICK"
    os.environ["POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS"] = "table_01,table_02,table_03,table_04,table_05,table_06"
    os.environ.pop("POKERVISION_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN", None)


@dataclass
class _BBox:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class _Slot:
    table_id: str
    bbox: _BBox


class _FakeActionButtonResult:
    def __init__(self, best_by_class: Dict[str, Dict[str, Any]]) -> None:
        self.status = "ok"
        self.best_by_class = best_by_class
        self.detected_classes = list(best_by_class.keys())
        self.raw_detection_count = len(best_by_class)
        self.processing_time_ms = 1
        self.warnings: List[str] = []
        self.errors: List[str] = []


def _base_buttons() -> Dict[str, Dict[str, Any]]:
    return {
        "FOLD": {"bbox_xyxy": [80, 610, 185, 660], "confidence": 0.99},
        "33%": {"bbox_xyxy": [230, 560, 315, 605], "confidence": 0.99},
        "50%": {"bbox_xyxy": [330, 560, 415, 605], "confidence": 0.99},
        "70%": {"bbox_xyxy": [430, 560, 515, 605], "confidence": 0.99},
        "98%": {"bbox_xyxy": [530, 560, 615, 605], "confidence": 0.99},
        "Call": {"bbox_xyxy": [300, 610, 420, 660], "confidence": 0.99},
        "Check/fold": {"bbox_xyxy": [80, 555, 205, 600], "confidence": 0.99},
        "Check": {"bbox_xyxy": [300, 555, 420, 600], "confidence": 0.99},
        "Bet/Raise": {"bbox_xyxy": [625, 610, 785, 660], "confidence": 0.99},
    }


def _load_cases() -> List[Dict[str, Any]]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Fixture must contain non-empty cases list.")
    return cases


def _import_runtime_modules():
    _configure_live_env()
    sys.path.insert(0, str(SNAPSHOT))
    import runtime.action_click_stub as click_stub  # type: ignore
    import logic.action_runtime_plan_builder as plan_builder  # type: ignore
    return click_stub, plan_builder


def _make_solver_decision(case: Dict[str, Any]) -> Dict[str, Any]:
    solver = dict(case["solver_decision"])
    solver.setdefault("status", "ok")
    solver.setdefault("source", "PokerVision_Solver_Preflop")
    solver.setdefault("table_id", "table_01")
    solver.setdefault("hand_id", f"hand_{case['case_id']}")
    solver.setdefault("frame_name", f"{case['case_id']}_preflop")
    return solver


def _make_action_decision_for_plan(case: Dict[str, Any]) -> Dict[str, Any]:
    solver = _make_solver_decision(case)
    raw_action = str(solver.get("raw_action") or solver.get("engine_action") or solver.get("action") or "")
    return {
        "schema_version": "action_decision_v1",
        "source": "Decision_JSON",
        "source_decision_frame_id": solver.get("frame_name", ""),
        "action": solver.get("action"),
        "size_policy": solver.get("size_pct"),
        "reason": f"v2_35_synthetic:{case['case_id']}",
        "solver_stub": False,
        "decision_context": {
            "solver_preflop_runtime_source": True,
            "solver_raw_action": raw_action,
            "solver_engine_action": solver.get("engine_action"),
            "solver_decision_id": solver.get("decision_id"),
        },
        "raw_action": raw_action,
        "engine_action": solver.get("engine_action"),
        "target_button_classes": case.get("solver_sequence", []),
    }


def _planned_solver_sequence(case: Dict[str, Any], plan_builder: Any) -> Dict[str, Any]:
    """Check only the V2.34/V2.35 Solver_Preflop raise sequence helper.

    The full Action_Runtime_Plan builder may validate broader legacy Action_Decision_JSON
    schema details that are unrelated to this synthetic real-click gate proof. This helper
    keeps the audit focused: user-facing Solver_Preflop raise sequence must remain correct,
    especially 5bet -> 50% -> Raise.
    """
    if not case.get("check_runtime_plan", False):
        return {"checked": False}
    try:
        helper = getattr(plan_builder, "_v234_solver_preflop_raise_sequence")
        seq = helper(_make_action_decision_for_plan(case), "bet_raise")
        return {"checked": True, "status": "ok", "sequence": list(seq)}
    except Exception as exc:  # pragma: no cover - diagnostic only
        return {"checked": True, "status": "error", "error": f"{type(exc).__name__}: {exc}"}


def _runtime_plan_alias(probe: Dict[str, Any]) -> Dict[str, Any] | None:
    """Backward-compatible compact runtime_plan view for tests and reports."""
    if not isinstance(probe, dict) or not probe.get("checked"):
        return None
    if probe.get("status") != "ok":
        return {"status": probe.get("status"), "error": probe.get("error")}
    return {
        "status": "ok",
        "planned_action": "bet_raise",
        "raise_branch_enabled": True,
        "target_sequence": list(probe.get("sequence") or []),
    }


def _run_case(case: Dict[str, Any], click_stub: Any, plan_builder: Any) -> Dict[str, Any]:
    solver = _make_solver_decision(case)
    buttons = _base_buttons()
    for missing in case.get("missing_buttons", []):
        buttons.pop(str(missing), None)
    fake_button_result = _FakeActionButtonResult(buttons)
    slot = _Slot(table_id=str(solver.get("table_id") or "table_01"), bbox=_BBox(0, 0, 900, 700))

    if hasattr(click_stub, "_EXECUTED_DECISION_AT"):
        click_stub._EXECUTED_DECISION_AT.clear()
    if hasattr(click_stub, "_CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS"):
        click_stub._CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS.clear()
    if hasattr(click_stub, "_CONTROLLED_LIVE_CLICK_EXECUTED_COUNT"):
        click_stub._CONTROLLED_LIVE_CLICK_EXECUTED_COUNT = 0

    mouse_calls: List[List[Dict[str, Any]]] = []

    def _mouse_spy(click_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        mouse_calls.append(click_points)
        return {"status": "executed_by_v2_35_test_spy", "physical_mouse_was_not_used": True, "click_points_count": len(click_points)}

    original_mouse = click_stub.execute_click_points_human_like
    click_stub.execute_click_points_human_like = _mouse_spy
    try:
        report = click_stub.build_and_maybe_execute_click_plan(
            solver_decision=solver,
            action_button_result=fake_button_result,
            slot=slot,
            active_confirmed=True,
        )
    finally:
        click_stub.execute_click_points_human_like = original_mouse

    gate = report.get("controlled_live_click_gate") if isinstance(report, dict) else {}
    if not isinstance(gate, dict):
        gate = {}
    plan_probe = _planned_solver_sequence(case, plan_builder)
    result = {
        "case_id": str(case["case_id"]),
        "kind": case.get("kind", "positive"),
        "status": report.get("status"),
        "message": report.get("message"),
        "action": report.get("action"),
        "raw_action": solver.get("raw_action"),
        "size_pct": solver.get("size_pct"),
        "target_sequence": report.get("target_sequence"),
        "expected_sequence": case.get("expected_sequence"),
        "gate_status": gate.get("status"),
        "gate_blockers": gate.get("blockers", []),
        "mouse_spy_called": bool(mouse_calls),
        "mouse_spy_call_count": len(mouse_calls),
        "expected_status": case.get("expected_status"),
        "expect_mouse_spy_called": bool(case.get("expect_mouse_spy_called", False)),
        "expected_gate_status": case.get("expected_gate_status"),
        "expected_blockers_any": case.get("expected_blockers_any", []),
        "runtime_plan_probe": plan_probe,
        "runtime_plan": _runtime_plan_alias(plan_probe),
        "expected_solver_sequence": case.get("solver_sequence"),
    }
    result["ok"] = _case_ok(result)
    return result


def _case_ok(result: Dict[str, Any]) -> bool:
    if result["status"] != result.get("expected_status"):
        return False
    if result.get("target_sequence") != result.get("expected_sequence"):
        return False
    if bool(result.get("mouse_spy_called")) != bool(result.get("expect_mouse_spy_called")):
        return False
    expected_gate = result.get("expected_gate_status")
    if expected_gate and result.get("gate_status") != expected_gate:
        return False
    blockers = set(str(x) for x in result.get("gate_blockers", []))
    for blocker in result.get("expected_blockers_any", []) or []:
        if str(blocker) not in blockers:
            return False

    probe = result.get("runtime_plan_probe")
    if isinstance(probe, dict) and probe.get("checked"):
        if probe.get("status") != "ok":
            return False
        expected_solver_sequence = result.get("expected_solver_sequence")
        if expected_solver_sequence and probe.get("sequence") != expected_solver_sequence:
            return False
    return True


def run_audit() -> Dict[str, Any]:
    click_stub, plan_builder = _import_runtime_modules()
    results = [_run_case(case, click_stub, plan_builder) for case in _load_cases()]
    return {
        "schema_version": "v2_35_synthetic_real_click_gate_e2e_report",
        "ok": all(item.get("ok") for item in results),
        "project_root": str(ROOT),
        "snapshot_root": str(SNAPSHOT),
        "cases_total": len(results),
        "cases_passed": sum(1 for item in results if item.get("ok")),
        "results": results,
    }


def _print_table(report: Dict[str, Any]) -> None:
    print("CASE                 ACTION      RAW_ACTION    SIZE  SEQUENCE                    GATE                               STATUS   SPY  PLAN_SEQ              OK")
    print("-" * 156)
    for item in report["results"]:
        seq = " -> ".join(str(x) for x in item.get("target_sequence") or [])
        probe = item.get("runtime_plan_probe") if isinstance(item.get("runtime_plan_probe"), dict) else {}
        plan_seq = " -> ".join(str(x) for x in probe.get("sequence") or []) if probe.get("checked") else "-"
        print(
            f"{item['case_id']:<20} {str(item.get('action')):<11} {str(item.get('raw_action')):<13} "
            f"{str(item.get('size_pct')):<5} {seq:<27} {str(item.get('gate_status')):<34} "
            f"{str(item.get('status')):<8} {str(item.get('mouse_spy_called')):<4} {plan_seq:<21} {item.get('ok')}"
        )
        if item.get("gate_blockers"):
            print(f"  blockers: {item.get('gate_blockers')}")
        if item.get("message") and item.get("status") != "clicked":
            print(f"  message: {item.get('message')}")
        if probe.get("checked") and probe.get("status") != "ok":
            print(f"  runtime_plan_probe_error: {probe}")
    print("-" * 156)
    print(f"V2.35_SYNTHETIC_REAL_CLICK_GATE_E2E_OK = {bool(report['ok'])}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", type=Path, default=None)
    args = parser.parse_args()
    report = run_audit()
    _print_table(report)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report_json={args.report_json}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
