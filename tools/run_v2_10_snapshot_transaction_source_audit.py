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
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v210_snapshot_transaction_source_audit"


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
    action_status: str = "skipped",
    decision_id: str = "decision_v210",
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


def _run_case(
    *,
    gate_cls: Any,
    name: str,
    runtime_action: dict[str, Any],
    dry_run_counts_as_completed: bool = True,
    open_transaction: bool = True,
    expected_completed: bool,
    expected_status: str,
    expected_reason: str,
    expected_branch: str | None = None,
) -> dict[str, Any]:
    gate = gate_cls(
        dry_run_counts_as_completed=dry_run_counts_as_completed,
        release_on_inactive=True,
    )
    table_id = f"table_{name}"

    begin_report = None
    if open_transaction:
        begin_report = gate.begin_action_cycle(
            table_id=table_id,
            action_event_id=f"evt_{name}",
            action_signature=f"sig_{name}",
        ).to_json()

    report = gate.finalize_from_runtime(
        table_id=table_id,
        runtime_action=runtime_action,
    )

    click_result = report.get("click_result") if isinstance(report.get("click_result"), dict) else {}
    clear_json_save_allowed = bool(report.get("click_completed"))
    click_result_for_clear = click_result if isinstance(click_result, dict) and clear_json_save_allowed else None

    checks = {
        "click_completed_expected": bool(report.get("click_completed")) is expected_completed,
        "status_expected": report.get("status") == expected_status,
        "reason_expected": report.get("reason") == expected_reason,
        "branch_expected": True if expected_branch is None else click_result.get("branch") == expected_branch,
        "click_result_available_for_clear_matches_completion": isinstance(click_result_for_clear, dict) is expected_completed,
    }

    return {
        "scenario": name,
        "dry_run_counts_as_completed": dry_run_counts_as_completed,
        "open_transaction": open_transaction,
        "begin_report": begin_report,
        "transaction_report": report,
        "derived_display_cycle_inputs": {
            "clear_json_save_allowed": clear_json_save_allowed,
            "click_result_for_clear_available": isinstance(click_result_for_clear, dict),
            "click_result_for_clear": click_result_for_clear,
        },
        "expected": {
            "click_completed": expected_completed,
            "status": expected_status,
            "reason": expected_reason,
            "branch": expected_branch,
        },
        "checks": checks,
        "ok": all(checks.values()),
    }


def main() -> int:
    if not GATE_PATH.exists():
        raise FileNotFoundError(GATE_PATH)
    if not DISPLAY_FILE.exists():
        raise FileNotFoundError(DISPLAY_FILE)

    _clean_output_dir()

    gate_module = _load_module("v210_table_action_transaction_gate", GATE_PATH)
    gate_cls = gate_module.TableActionTransactionGate

    display_text = DISPLAY_FILE.read_text(encoding="utf-8")
    gate_text = GATE_PATH.read_text(encoding="utf-8")

    static_checks = {
        "display_finalize_from_runtime_present": "finalize_from_runtime(" in display_text,
        "display_clear_json_save_allowed_from_click_completed": "clear_json_save_allowed = bool(transaction_runtime_report.get(\"click_completed\"))" in display_text,
        "display_click_result_for_clear_requires_save_allowed": "if isinstance(click_result, dict) and clear_json_save_allowed:" in display_text,
        "gate_completed_statuses_present": "_COMPLETED_STATUSES = {\"clicked\", \"confirmed\", \"dry_run\"}" in gate_text,
        "gate_failed_statuses_present": "_FAILED_STATUSES = {\"blocked\", \"error\", \"timeout\", \"failed\"}" in gate_text,
        "gate_dry_run_config_present": "dry_run_counts_as_completed" in gate_text,
        "gate_service_priority_present": "if service_status in _COMPLETED_STATUSES or service_status in _FAILED_STATUSES" in gate_text,
    }

    cases = [
        _run_case(
            gate_cls=gate_cls,
            name="action_button_dry_run_completed",
            runtime_action=_runtime_action(service_status="skipped", action_status="dry_run", decision_id="d1"),
            expected_completed=True,
            expected_status="completed",
            expected_reason="click_cycle_completed",
            expected_branch="action_button",
        ),
        _run_case(
            gate_cls=gate_cls,
            name="action_button_clicked_completed",
            runtime_action=_runtime_action(service_status="skipped", action_status="clicked", decision_id="d2", dry_run=False, real_click_enabled=True),
            expected_completed=True,
            expected_status="completed",
            expected_reason="click_cycle_completed",
            expected_branch="action_button",
        ),
        _run_case(
            gate_cls=gate_cls,
            name="action_button_confirmed_completed",
            runtime_action=_runtime_action(service_status="skipped", action_status="confirmed", decision_id="d3", dry_run=False, real_click_enabled=True),
            expected_completed=True,
            expected_status="completed",
            expected_reason="click_cycle_completed",
            expected_branch="action_button",
        ),
        _run_case(
            gate_cls=gate_cls,
            name="action_button_skipped_pending",
            runtime_action=_runtime_action(service_status="skipped", action_status="skipped", decision_id="d4", guard_passed=False),
            expected_completed=False,
            expected_status="pending",
            expected_reason="click_cycle_not_completed",
            expected_branch="action_button",
        ),
        _run_case(
            gate_cls=gate_cls,
            name="action_button_blocked_failed",
            runtime_action=_runtime_action(service_status="skipped", action_status="blocked", decision_id="d5", guard_passed=False),
            expected_completed=False,
            expected_status="failed",
            expected_reason="click_cycle_not_completed",
            expected_branch="action_button",
        ),
        _run_case(
            gate_cls=gate_cls,
            name="service_dry_run_completed",
            runtime_action=_runtime_action(service_status="dry_run", action_status="blocked", decision_id="d6"),
            expected_completed=True,
            expected_status="completed",
            expected_reason="click_cycle_completed",
            expected_branch="service",
        ),
        _run_case(
            gate_cls=gate_cls,
            name="service_blocked_overrides_action_dry_run",
            runtime_action=_runtime_action(service_status="blocked", action_status="dry_run", decision_id="d7", guard_passed=False),
            expected_completed=False,
            expected_status="failed",
            expected_reason="click_cycle_not_completed",
            expected_branch="service",
        ),
        _run_case(
            gate_cls=gate_cls,
            name="dry_run_not_completed_when_config_false",
            runtime_action=_runtime_action(service_status="skipped", action_status="dry_run", decision_id="d8"),
            dry_run_counts_as_completed=False,
            expected_completed=False,
            expected_status="failed",
            expected_reason="click_cycle_not_completed",
            expected_branch="action_button",
        ),
        _run_case(
            gate_cls=gate_cls,
            name="no_open_transaction_reports_skipped_but_completed_signal_can_exist",
            runtime_action=_runtime_action(service_status="skipped", action_status="dry_run", decision_id="d9"),
            open_transaction=False,
            expected_completed=True,
            expected_status="skipped",
            expected_reason="no_open_transaction",
            expected_branch="action_button",
        ),
    ]

    ok_count = len([case for case in cases if case["ok"] is True])
    bad_count = len(cases) - ok_count

    report = {
        "schema": "pokervision_solver_preflop_v210_snapshot_transaction_source_audit_v1",
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
        "scenario_count": len(cases),
        "ok_count": ok_count,
        "bad_count": bad_count,
        "cases": cases,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
