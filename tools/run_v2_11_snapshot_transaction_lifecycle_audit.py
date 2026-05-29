from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
GATE_PATH = SNAPSHOT_ROOT / "logic" / "table_action_transaction_gate.py"
DISPLAY_FILE = SNAPSHOT_ROOT / "display_analysis_cycle.py"
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v211_snapshot_transaction_lifecycle_audit"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _clean_output_dir() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _runtime_action(
    *,
    service_status: str = "skipped",
    action_status: str = "dry_run",
    decision_id: str = "decision_v211",
    dry_run: bool = True,
    real_click_enabled: bool = False,
    guard_passed: bool = True,
) -> dict[str, Any]:
    return {
        "service": {
            "status": service_status,
            "reason": f"service_{service_status}",
            "decision_id": decision_id,
            "solver_action": "fold",
            "dry_run": dry_run,
            "real_click_enabled": real_click_enabled,
            "guard_passed": guard_passed,
            "message": f"service branch status={service_status}",
        },
        "action_button": {
            "status": action_status,
            "reason": f"action_button_{action_status}",
            "decision_id": decision_id,
            "solver_action": "fold",
            "dry_run": dry_run,
            "real_click_enabled": real_click_enabled,
            "guard_passed": guard_passed,
            "message": f"action_button branch status={action_status}",
        },
    }


def _to_json(decision: Any) -> dict[str, Any]:
    if hasattr(decision, "to_json"):
        payload = decision.to_json()
        return payload if isinstance(payload, dict) else {}
    return {}


def _snapshot(gate: Any, table_id: str) -> dict[str, Any] | None:
    payload = gate.snapshot(table_id)
    return payload if isinstance(payload, dict) else None


def _run_full_success(gate_cls: Any) -> dict[str, Any]:
    gate = gate_cls(dry_run_counts_as_completed=True, release_on_inactive=True)
    table_id = "table_v211_full_success"

    begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    action = gate.begin_action_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    final = gate.finalize_from_runtime(
        table_id=table_id,
        runtime_action=_runtime_action(action_status="dry_run", decision_id="d_v211_success"),
    )
    after_snapshot = _snapshot(gate, table_id)
    next_begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_b", action_signature="sig_b")

    checks = {
        "begin_started": begin.should_process is True and begin.status == "started" and begin.phase == "analyzing",
        "action_continued": action.should_process is True and action.status == "continued" and action.phase == "waiting_click",
        "final_completed": final.get("status") == "completed" and final.get("click_completed") is True and final.get("phase") == "click_done",
        "state_released_after_completion": after_snapshot is None,
        "next_lifecycle_allowed": next_begin.should_process is True and next_begin.status == "started",
    }

    return {
        "scenario": "full_success_lifecycle_releases_table",
        "begin": _to_json(begin),
        "action": _to_json(action),
        "final": final,
        "after_snapshot": after_snapshot,
        "next_begin": _to_json(next_begin),
        "checks": checks,
        "ok": all(checks.values()),
    }


def _run_early_duplicate_blocks(gate_cls: Any) -> dict[str, Any]:
    gate = gate_cls(dry_run_counts_as_completed=True, release_on_inactive=True)
    table_id = "table_v211_early_duplicate"

    first = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    second = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_b", action_signature="sig_b")
    snapshot = _snapshot(gate, table_id)

    checks = {
        "first_started": first.should_process is True and first.status == "started",
        "second_blocked": second.should_process is False and second.status == "blocked",
        "blocked_reason": second.reason == "table_lifecycle_already_open_before_analysis",
        "locked_phase_analyzing": second.phase == "analyzing",
        "state_still_open": isinstance(snapshot, dict) and snapshot.get("phase") == "analyzing",
    }

    return {
        "scenario": "early_duplicate_blocks_heavy_analysis",
        "first": _to_json(first),
        "second": _to_json(second),
        "snapshot": snapshot,
        "checks": checks,
        "ok": all(checks.values()),
    }


def _run_late_duplicate_action_blocks(gate_cls: Any) -> dict[str, Any]:
    gate = gate_cls(dry_run_counts_as_completed=True, release_on_inactive=True)
    table_id = "table_v211_late_duplicate"

    begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    first_action = gate.begin_action_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    second_action = gate.begin_action_cycle(table_id=table_id, action_event_id="evt_b", action_signature="sig_b")
    snapshot = _snapshot(gate, table_id)

    checks = {
        "begin_started": begin.should_process is True,
        "first_action_continued": first_action.should_process is True and first_action.status == "continued",
        "second_action_blocked": second_action.should_process is False and second_action.status == "blocked",
        "blocked_reason": second_action.reason == "table_action_transaction_already_open",
        "state_waiting_click": isinstance(snapshot, dict) and snapshot.get("phase") == "waiting_click",
    }

    return {
        "scenario": "late_duplicate_action_cycle_blocks",
        "begin": _to_json(begin),
        "first_action": _to_json(first_action),
        "second_action": _to_json(second_action),
        "snapshot": snapshot,
        "checks": checks,
        "ok": all(checks.values()),
    }


def _run_skipped_runtime_pending_then_inactive_release(gate_cls: Any) -> dict[str, Any]:
    gate = gate_cls(dry_run_counts_as_completed=True, release_on_inactive=True)
    table_id = "table_v211_skipped_pending"

    begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    action = gate.begin_action_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    final = gate.finalize_from_runtime(
        table_id=table_id,
        runtime_action=_runtime_action(action_status="skipped", decision_id="d_v211_skipped", guard_passed=False),
    )
    blocked = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_b", action_signature="sig_b")
    inactive_release = gate.observe_inactive(table_id)
    after_release_snapshot = _snapshot(gate, table_id)
    next_begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_c", action_signature="sig_c")

    checks = {
        "begin_started": begin.should_process is True,
        "action_continued": action.should_process is True,
        "final_pending": final.get("status") == "pending" and final.get("phase") == "click_pending" and final.get("click_completed") is False,
        "new_analysis_blocked_while_pending": blocked.should_process is False and blocked.reason == "table_lifecycle_already_open_before_analysis",
        "inactive_released": isinstance(inactive_release, dict) and inactive_release.get("status") == "aborted",
        "state_removed_after_inactive": after_release_snapshot is None,
        "next_lifecycle_allowed": next_begin.should_process is True,
    }

    return {
        "scenario": "skipped_runtime_pending_then_inactive_release",
        "begin": _to_json(begin),
        "action": _to_json(action),
        "final": final,
        "blocked": _to_json(blocked),
        "inactive_release": inactive_release,
        "after_release_snapshot": after_release_snapshot,
        "next_begin": _to_json(next_begin),
        "checks": checks,
        "ok": all(checks.values()),
    }


def _run_blocked_runtime_failed_until_abort(gate_cls: Any) -> dict[str, Any]:
    gate = gate_cls(dry_run_counts_as_completed=True, release_on_inactive=True)
    table_id = "table_v211_blocked_failed"

    begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    action = gate.begin_action_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    final = gate.finalize_from_runtime(
        table_id=table_id,
        runtime_action=_runtime_action(action_status="blocked", decision_id="d_v211_blocked", guard_passed=False),
    )
    second_action = gate.begin_action_cycle(table_id=table_id, action_event_id="evt_b", action_signature="sig_b")
    abort = gate.abort_analysis_cycle(table_id=table_id, reason="manual_failed_runtime_release", message="manual release")
    after_abort_snapshot = _snapshot(gate, table_id)
    next_begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_c", action_signature="sig_c")

    checks = {
        "begin_started": begin.should_process is True,
        "action_continued": action.should_process is True,
        "final_failed": final.get("status") == "failed" and final.get("phase") == "click_failed" and final.get("click_completed") is False,
        "second_action_blocked": second_action.should_process is False and second_action.reason == "table_action_transaction_already_open",
        "abort_released": isinstance(abort, dict) and abort.get("status") == "aborted" and abort.get("reason") == "manual_failed_runtime_release",
        "state_removed_after_abort": after_abort_snapshot is None,
        "next_lifecycle_allowed": next_begin.should_process is True,
    }

    return {
        "scenario": "blocked_runtime_failed_until_abort",
        "begin": _to_json(begin),
        "action": _to_json(action),
        "final": final,
        "second_action": _to_json(second_action),
        "abort": abort,
        "after_abort_snapshot": after_abort_snapshot,
        "next_begin": _to_json(next_begin),
        "checks": checks,
        "ok": all(checks.values()),
    }


def _run_failed_active_finalization_release(gate_cls: Any) -> dict[str, Any]:
    gate = gate_cls(dry_run_counts_as_completed=True, release_on_inactive=True)
    table_id = "table_v211_failed_active_release"

    begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    release = gate.release_failed_active_finalization(
        table_id=table_id,
        reason="active_runtime_plan_not_built",
        message="runtime plan missing",
    )
    after_release_snapshot = _snapshot(gate, table_id)
    next_begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_b", action_signature="sig_b")

    checks = {
        "begin_started": begin.should_process is True and begin.phase == "analyzing",
        "release_aborted": isinstance(release, dict) and release.get("status") == "aborted",
        "release_reason": release.get("reason") == "active_runtime_plan_not_built",
        "release_click_completed_false": release.get("click_completed") is False,
        "state_removed_after_release": after_release_snapshot is None,
        "next_lifecycle_allowed": next_begin.should_process is True,
    }

    return {
        "scenario": "failed_active_finalization_release",
        "begin": _to_json(begin),
        "release": release,
        "after_release_snapshot": after_release_snapshot,
        "next_begin": _to_json(next_begin),
        "checks": checks,
        "ok": all(checks.values()),
    }


def _run_observe_inactive_without_release_keeps_lock(gate_cls: Any) -> dict[str, Any]:
    gate = gate_cls(dry_run_counts_as_completed=True, release_on_inactive=False)
    table_id = "table_v211_inactive_no_release"

    begin = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_a", action_signature="sig_a")
    inactive = gate.observe_inactive(table_id)
    snapshot = _snapshot(gate, table_id)
    blocked = gate.begin_analysis_cycle(table_id=table_id, action_event_id="evt_b", action_signature="sig_b")

    checks = {
        "begin_started": begin.should_process is True,
        "inactive_returns_snapshot": isinstance(inactive, dict) and inactive.get("phase") == "analyzing",
        "state_kept": isinstance(snapshot, dict) and snapshot.get("phase") == "analyzing",
        "next_analysis_still_blocked": blocked.should_process is False and blocked.reason == "table_lifecycle_already_open_before_analysis",
    }

    return {
        "scenario": "observe_inactive_without_release_keeps_lock",
        "begin": _to_json(begin),
        "inactive": inactive,
        "snapshot": snapshot,
        "blocked": _to_json(blocked),
        "checks": checks,
        "ok": all(checks.values()),
    }


def main() -> int:
    if not GATE_PATH.exists():
        raise FileNotFoundError(GATE_PATH)
    if not DISPLAY_FILE.exists():
        raise FileNotFoundError(DISPLAY_FILE)

    _clean_output_dir()

    gate_module = _load_module("v211_table_action_transaction_gate", GATE_PATH)
    gate_cls = gate_module.TableActionTransactionGate

    display_text = DISPLAY_FILE.read_text(encoding="utf-8")
    gate_text = GATE_PATH.read_text(encoding="utf-8")

    static_checks = {
        "display_begin_analysis_call_present": "begin_analysis_cycle(" in display_text,
        "display_begin_action_call_present": "begin_action_cycle(" in display_text,
        "display_finalize_runtime_call_present": "finalize_from_runtime(" in display_text,
        "display_observe_inactive_call_present": "observe_inactive(slot.table_id)" in display_text,
        "display_failed_active_release_call_present": "release_failed_active_finalization(" in display_text,
        "gate_open_phases_include_click_pending": '"click_pending"' in gate_text,
        "gate_open_phases_include_click_failed": '"click_failed"' in gate_text,
        "gate_terminal_phases_present": '_TERMINAL_PHASES = {"released", "click_done", "aborted"}' in gate_text,
    }

    scenarios = [
        _run_full_success(gate_cls),
        _run_early_duplicate_blocks(gate_cls),
        _run_late_duplicate_action_blocks(gate_cls),
        _run_skipped_runtime_pending_then_inactive_release(gate_cls),
        _run_blocked_runtime_failed_until_abort(gate_cls),
        _run_failed_active_finalization_release(gate_cls),
        _run_observe_inactive_without_release_keeps_lock(gate_cls),
    ]

    ok_count = len([item for item in scenarios if item["ok"] is True])
    bad_count = len(scenarios) - ok_count

    report = {
        "schema": "pokervision_solver_preflop_v211_snapshot_transaction_lifecycle_audit_v1",
        "status": "ok" if all(static_checks.values()) and bad_count == 0 else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_gate": str(GATE_PATH),
        "snapshot_display": str(DISPLAY_FILE),
        "out_dir": str(OUT_DIR),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "static_checks": static_checks,
        "scenario_count": len(scenarios),
        "ok_count": ok_count,
        "bad_count": bad_count,
        "scenarios": scenarios,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
