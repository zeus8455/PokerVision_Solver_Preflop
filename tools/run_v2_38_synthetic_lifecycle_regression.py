from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DEFAULT_REPORT_JSON = ROOT / "outputs" / "v2_38_synthetic_lifecycle_regression.json"


def _ensure_snapshot_import() -> None:
    if str(SNAPSHOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT))


def _players_block(*, hero_cards: List[str] | None = None, hero_chips: float = 0.5, villain_chips: float = 1.0) -> Dict[str, Any]:
    cards = list(hero_cards or ["As", "Ks"])
    return {
        "seats": {
            "Player_seat1": {
                "position": "CO",
                "hero": True,
                "cards": cards,
                "fold": False,
                "sitout": False,
                "chips": {"detect": True, "value": hero_chips},
                "stack": {"all_in": False},
            },
            "Player_seat2": {
                "position": "BTN",
                "hero": False,
                "cards": [],
                "fold": False,
                "sitout": False,
                "chips": {"detect": True, "value": villain_chips},
                "stack": {"all_in": False},
            },
        }
    }


def _table_structure_block(*, pot: float = 1.5, board_cards: List[str] | None = None) -> Dict[str, Any]:
    return {
        "classes": {
            "Board": {"cards": list(board_cards or [])},
            "Total_pot": {"value": pot},
        }
    }


def _decision_to_dict(decision: Any) -> Dict[str, Any]:
    if hasattr(decision, "to_json"):
        return dict(decision.to_json())
    try:
        return asdict(decision)
    except Exception:
        return {"repr": repr(decision)}


def _runtime_action_block(*, status: str, decision_id: str = "v238_decision_001", action: str = "fold") -> Dict[str, Any]:
    return {
        "service": {"status": "skipped"},
        "action_button": {
            "status": status,
            "decision_id": decision_id,
            "action": action,
            "solver_action": action,
            "size_pct": None,
            "dry_run": status == "dry_run",
            "real_click_enabled": status == "clicked",
            "guard_passed": status in {"clicked", "dry_run"},
            "message": f"v238 synthetic runtime_action status={status}",
        },
    }


def _run_action_event_gate_regression() -> Dict[str, Any]:
    _ensure_snapshot_import()
    from display_analysis_cycle import ActionEventGate  # type: ignore

    gate = ActionEventGate(inactive_reset_passes=2)
    table_id = "table_01"
    kwargs = {
        "table_id": table_id,
        "hero_cards": ["As", "Ks"],
        "street": "preflop",
        "table_structure_block": _table_structure_block(),
        "players_block": _players_block(),
    }

    first = gate.evaluate_active(**kwargs)
    duplicate = gate.evaluate_active(**kwargs)
    gate.observe_inactive(table_id)
    after_one_inactive = gate.evaluate_active(**kwargs)

    # Rebuild a new gate to test full inactive reset deterministically without the after_one_inactive call
    gate2 = ActionEventGate(inactive_reset_passes=2)
    first2 = gate2.evaluate_active(**kwargs)
    duplicate2 = gate2.evaluate_active(**kwargs)
    gate2.observe_inactive(table_id)
    gate2.observe_inactive(table_id)
    after_full_inactive = gate2.evaluate_active(**kwargs)

    checks = {
        "first_new_active_ok": bool(first.should_process) and first.reason == "new_active_action_event" and bool(first.action_event_id),
        "duplicate_blocked_ok": (not bool(duplicate.should_process)) and duplicate.reason == "duplicate_active_frame_blocked" and duplicate.duplicate_of == first.action_event_id,
        "one_inactive_not_enough_ok": (not bool(after_one_inactive.should_process)) and after_one_inactive.reason == "duplicate_active_frame_blocked",
        "full_inactive_releases_ok": bool(after_full_inactive.should_process) and after_full_inactive.reason == "new_active_action_event" and bool(after_full_inactive.action_event_id),
        "duplicate2_blocked_ok": (not bool(duplicate2.should_process)) and duplicate2.reason == "duplicate_active_frame_blocked" and duplicate2.duplicate_of == first2.action_event_id,
    }
    return {
        "case_id": "action_event_duplicate_and_inactive_release",
        "first": _decision_to_dict(first),
        "duplicate": _decision_to_dict(duplicate),
        "after_one_inactive": _decision_to_dict(after_one_inactive),
        "after_full_inactive": _decision_to_dict(after_full_inactive),
        "checks": checks,
        "ok": all(checks.values()),
    }


def _v230_duplicate_retry_allowed(*, reason: str, has_runtime_plan: bool, has_final_clear: bool) -> Dict[str, Any]:
    allowed = reason == "duplicate_active_frame_blocked" and not bool(has_runtime_plan) and not bool(has_final_clear)
    return {
        "allowed": bool(allowed),
        "reason": "v230_duplicate_active_runtime_retry_without_completed_runtime" if allowed else "duplicate_retry_not_allowed",
        "inputs": {
            "reason": reason,
            "has_runtime_plan": bool(has_runtime_plan),
            "has_final_clear": bool(has_final_clear),
        },
    }


def _run_v230_retry_policy_regression() -> Dict[str, Any]:
    cases = [
        ("unfinished_duplicate_allows_retry", "duplicate_active_frame_blocked", False, False, True),
        ("duplicate_with_runtime_plan_blocks_retry", "duplicate_active_frame_blocked", True, False, False),
        ("duplicate_with_final_clear_blocks_retry", "duplicate_active_frame_blocked", False, True, False),
        ("non_duplicate_blocks_retry", "new_active_action_event", False, False, False),
    ]
    results = []
    for case_id, reason, has_runtime_plan, has_final_clear, expected in cases:
        report = _v230_duplicate_retry_allowed(reason=reason, has_runtime_plan=has_runtime_plan, has_final_clear=has_final_clear)
        ok = bool(report["allowed"]) == bool(expected)
        results.append({"case_id": case_id, **report, "expected_allowed": bool(expected), "ok": ok})
    return {"case_id": "v230_duplicate_active_runtime_retry_policy", "results": results, "ok": all(item["ok"] for item in results)}


def _run_table_transaction_gate_regression() -> Dict[str, Any]:
    _ensure_snapshot_import()
    from logic.table_action_transaction_gate import TableActionTransactionGate  # type: ignore

    table_id = "table_01"
    gate = TableActionTransactionGate(dry_run_counts_as_completed=True, release_on_inactive=True)

    first = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    blocked = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_b", action_signature="sig_b")
    abort = gate.abort_analysis_cycle(table_id=table_id, reason="v238_no_action_runtime_candidate", message="Synthetic early lifecycle release")
    after_abort = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_c", action_signature="sig_c")

    gate2 = TableActionTransactionGate(dry_run_counts_as_completed=True, release_on_inactive=True)
    a2 = gate2.begin_analysis_cycle(table_id=table_id, action_event_id="evt_click", action_signature="sig_click")
    action_cycle = gate2.begin_action_cycle(table_id=table_id, action_event_id="evt_click", action_signature="sig_click")
    completed = gate2.finalize_from_runtime(table_id=table_id, runtime_action=_runtime_action_block(status="clicked", decision_id="v238_clicked", action="bet_raise"))
    after_completed = gate2.begin_analysis_cycle(table_id=table_id, action_event_id="evt_after_click", action_signature="sig_after_click")

    gate3 = TableActionTransactionGate(dry_run_counts_as_completed=True, release_on_inactive=True)
    b3 = gate3.begin_analysis_cycle(table_id=table_id, action_event_id="evt_blocked", action_signature="sig_blocked")
    action_cycle3 = gate3.begin_action_cycle(table_id=table_id, action_event_id="evt_blocked", action_signature="sig_blocked")
    not_completed = gate3.finalize_from_runtime(table_id=table_id, runtime_action=_runtime_action_block(status="blocked", decision_id="v238_blocked", action="fold"))
    still_locked = gate3.begin_analysis_cycle(table_id=table_id, action_event_id="evt_should_block", action_signature="sig_should_block")
    release_failed = gate3.release_failed_active_finalization(table_id=table_id, reason="v238_no_final_without_click_result")
    after_release_failed = gate3.begin_analysis_cycle(table_id=table_id, action_event_id="evt_after_release", action_signature="sig_after_release")

    gate4 = TableActionTransactionGate(dry_run_counts_as_completed=True, release_on_inactive=True)
    gate4.begin_analysis_cycle(table_id=table_id, action_event_id="evt_inactive", action_signature="sig_inactive")
    inactive_release = gate4.observe_inactive(table_id)
    after_inactive = gate4.begin_analysis_cycle(table_id=table_id, action_event_id="evt_after_inactive", action_signature="sig_after_inactive")

    checks = {
        "first_analysis_starts_ok": bool(first.should_process) and first.reason == "new_active_table_analysis_lifecycle_started",
        "second_analysis_blocked_ok": (not bool(blocked.should_process)) and blocked.reason == "table_lifecycle_already_open_before_analysis",
        "abort_releases_ok": abort.get("status") == "aborted" and bool(after_abort.should_process),
        "action_cycle_started_ok": bool(a2.should_process) and bool(action_cycle.should_process) and action_cycle.reason == "active_table_lifecycle_entered_action_runtime",
        "clicked_completes_and_releases_ok": completed.get("status") == "completed" and completed.get("click_completed") is True and bool(after_completed.should_process),
        "blocked_click_does_not_publish_final_ok": not_completed.get("click_completed") is False and not_completed.get("status") in {"failed", "pending"},
        "blocked_click_keeps_lifecycle_until_release_ok": (not bool(still_locked.should_process)) and still_locked.reason == "table_lifecycle_already_open_before_analysis",
        "failed_finalization_release_ok": release_failed.get("status") == "aborted" and bool(after_release_failed.should_process),
        "inactive_releases_lifecycle_ok": isinstance(inactive_release, dict) and inactive_release.get("reason") == "active_disappeared_before_click_completion" and bool(after_inactive.should_process),
    }

    return {
        "case_id": "table_action_transaction_lifecycle",
        "first": _decision_to_dict(first),
        "blocked": _decision_to_dict(blocked),
        "abort": abort,
        "after_abort": _decision_to_dict(after_abort),
        "action_cycle": _decision_to_dict(action_cycle),
        "completed": completed,
        "after_completed": _decision_to_dict(after_completed),
        "not_completed": not_completed,
        "still_locked": _decision_to_dict(still_locked),
        "release_failed": release_failed,
        "after_release_failed": _decision_to_dict(after_release_failed),
        "inactive_release": inactive_release,
        "after_inactive": _decision_to_dict(after_inactive),
        "checks": checks,
        "ok": all(checks.values()),
    }


def _run_dry_run_completion_policy_regression() -> Dict[str, Any]:
    _ensure_snapshot_import()
    from logic.table_action_transaction_gate import TableActionTransactionGate  # type: ignore

    table_id = "table_01"

    gate_true = TableActionTransactionGate(dry_run_counts_as_completed=True, release_on_inactive=True)
    gate_true.begin_analysis_cycle(table_id=table_id, action_event_id="evt_dry_true", action_signature="sig_dry_true")
    gate_true.begin_action_cycle(table_id=table_id, action_event_id="evt_dry_true", action_signature="sig_dry_true")
    dry_true = gate_true.finalize_from_runtime(table_id=table_id, runtime_action=_runtime_action_block(status="dry_run", decision_id="v238_dry_true", action="fold"))

    gate_false = TableActionTransactionGate(dry_run_counts_as_completed=False, release_on_inactive=True)
    gate_false.begin_analysis_cycle(table_id=table_id, action_event_id="evt_dry_false", action_signature="sig_dry_false")
    gate_false.begin_action_cycle(table_id=table_id, action_event_id="evt_dry_false", action_signature="sig_dry_false")
    dry_false = gate_false.finalize_from_runtime(table_id=table_id, runtime_action=_runtime_action_block(status="dry_run", decision_id="v238_dry_false", action="fold"))

    checks = {
        "dry_run_counts_as_completed_true_ok": dry_true.get("status") == "completed" and dry_true.get("click_completed") is True,
        "dry_run_counts_as_completed_false_blocks_final_ok": dry_false.get("status") in {"pending", "failed"} and dry_false.get("click_completed") is False,
    }
    return {"case_id": "dry_run_completion_policy", "dry_true": dry_true, "dry_false": dry_false, "checks": checks, "ok": all(checks.values())}


def _fake_action_button_result() -> Dict[str, Any]:
    return {
        "status": "ok",
        "detected_classes": ["FOLD", "Call", "Check", "Bet/Raise"],
        "best_by_class": {
            "FOLD": {"bbox_xyxy": [10, 10, 110, 60], "confidence": 0.99},
            "Call": {"bbox_xyxy": [130, 10, 230, 60], "confidence": 0.99},
            "Check": {"bbox_xyxy": [250, 10, 350, 60], "confidence": 0.99},
            "Bet/Raise": {"bbox_xyxy": [370, 10, 500, 60], "confidence": 0.99},
        },
    }


def _run_click_no_repeat_regression() -> Dict[str, Any]:
    _ensure_snapshot_import()
    import runtime.action_click_stub as click_stub  # type: ignore

    # Make this proof deterministic and independent of external live-run env.
    click_stub.V11_CLICK_DRY_RUN = False
    click_stub.V11_REAL_MOUSE_CLICK_ENABLED = True
    click_stub.V11_CLICK_REQUIRE_ACTIVE = True
    click_stub.V11_CLICK_REQUIRE_BUTTON_DETECTION = True
    click_stub.V11_CLICK_STUB_ENABLED = True
    click_stub.V31_CONTROLLED_LIVE_CLICK_GATE_ENABLED = True
    click_stub.V31_CONTROLLED_LIVE_CLICK_REQUIRE_ENV_CONFIRM = True
    click_stub.V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED = True
    click_stub.V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN = 0
    os.environ[str(click_stub.V31_CONTROLLED_LIVE_CLICK_ENV_VAR)] = str(click_stub.V31_CONTROLLED_LIVE_CLICK_ENV_VALUE)
    os.environ[str(click_stub.V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR)] = "table_01"

    # Reset process-local click memory.
    if hasattr(click_stub, "_EXECUTED_DECISION_AT"):
        click_stub._EXECUTED_DECISION_AT.clear()
    if hasattr(click_stub, "_CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS"):
        click_stub._CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS.clear()
    if hasattr(click_stub, "_CONTROLLED_LIVE_CLICK_EXECUTED_COUNT"):
        click_stub._CONTROLLED_LIVE_CLICK_EXECUTED_COUNT = 0

    class _BBox:
        def __init__(self) -> None:
            self.x1 = 0
            self.y1 = 0
            self.x2 = 900
            self.y2 = 700

    class _Slot:
        table_id = "table_01"
        bbox = _BBox()

    mouse_calls: List[List[Dict[str, Any]]] = []

    def _mouse_spy(click_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        mouse_calls.append(click_points)
        return {"status": "executed_by_v238_mouse_spy", "click_points_count": len(click_points)}

    original_mouse = click_stub.execute_click_points_human_like
    click_stub.execute_click_points_human_like = _mouse_spy
    try:
        solver_decision = {
            "status": "ok",
            "source": "PokerVision_Solver_Preflop",
            "decision_id": "v238_no_repeat_decision",
            "table_id": "table_01",
            "hand_id": "hand_v238",
            "frame_name": "table_01_hand_v238_preflop_01",
            "action": "fold",
            "raw_action": "fold",
            "size_pct": None,
        }
        first = click_stub.build_and_maybe_execute_click_plan(
            solver_decision=dict(solver_decision),
            action_button_result=_fake_action_button_result(),
            slot=_Slot(),
            active_confirmed=True,
        )
        second = click_stub.build_and_maybe_execute_click_plan(
            solver_decision=dict(solver_decision),
            action_button_result=_fake_action_button_result(),
            slot=_Slot(),
            active_confirmed=True,
        )
    finally:
        click_stub.execute_click_points_human_like = original_mouse

    checks = {
        "first_clicked_ok": first.get("status") == "clicked" and bool(first.get("guard_passed")) and len(mouse_calls) == 1,
        "second_same_decision_blocked_ok": second.get("status") == "blocked" and "already executed" in str(second.get("message") or "").lower() and len(mouse_calls) == 1,
        "controlled_gate_recorded_first_ok": isinstance(first.get("controlled_live_click_gate"), dict) and first["controlled_live_click_gate"].get("status") == "CONTROLLED_LIVE_CLICK_GATE_PASSED",
    }
    return {"case_id": "click_no_repeat_same_decision", "first": first, "second": second, "mouse_calls_count": len(mouse_calls), "checks": checks, "ok": all(checks.values())}


def run_audit() -> Dict[str, Any]:
    sections = [
        _run_action_event_gate_regression(),
        _run_v230_retry_policy_regression(),
        _run_table_transaction_gate_regression(),
        _run_dry_run_completion_policy_regression(),
        _run_click_no_repeat_regression(),
    ]
    return {
        "schema_version": "v2_38_synthetic_lifecycle_regression_report_v1",
        "ok": all(bool(item.get("ok")) for item in sections),
        "project_root": str(ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "sections": sections,
    }


def _print_report(report: Dict[str, Any]) -> None:
    print("V2.38 SYNTHETIC LIFECYCLE REGRESSION")
    print("CASE                                         OK")
    print("-" * 64)
    for section in report.get("sections", []):
        print(f"{str(section.get('case_id')):<44} {bool(section.get('ok'))}")
        checks = section.get("checks")
        if isinstance(checks, dict):
            for name, value in checks.items():
                print(f"  {name:<42} {bool(value)}")
        if section.get("case_id") == "v230_duplicate_active_runtime_retry_policy":
            for item in section.get("results", []):
                print(f"  {str(item.get('case_id')):<42} {bool(item.get('ok'))}")
    print("-" * 64)
    print(f"V2.38_SYNTHETIC_LIFECYCLE_REGRESSION_OK = {bool(report.get('ok'))}")


def main() -> int:
    parser = argparse.ArgumentParser(description="V2.38 synthetic lifecycle regression audit")
    parser.add_argument("--report-json", default=str(DEFAULT_REPORT_JSON))
    args = parser.parse_args()

    report = run_audit()
    report_path = Path(args.report_json)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _print_report(report)
    print(f"report_json={report_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
