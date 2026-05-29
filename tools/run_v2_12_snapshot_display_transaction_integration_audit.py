from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DISPLAY_FILE = SNAPSHOT_ROOT / "display_analysis_cycle.py"
GATE_PATH = SNAPSHOT_ROOT / "logic" / "table_action_transaction_gate.py"
PENDING_ROOT = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle" / "Clear_JSON_Pending"
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v212_snapshot_display_transaction_integration_audit"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_output_dir() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _discover_one_preflop_file() -> Path:
    files = sorted(PENDING_ROOT.glob("table_*/*preflop*.json"))
    if not files:
        raise RuntimeError(f"No preflop Pending Clear_JSON files found under {PENDING_ROOT}")
    return files[0]


def _table_id_from_path(path: Path) -> str:
    parent = path.parent.name
    return parent if parent.startswith("table_") else "table_01"


def _runtime_action(
    *,
    service_status: str = "skipped",
    action_status: str = "dry_run",
    decision_id: str = "decision_v212",
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


def _make_dark_state(
    *,
    table_id: str,
    frame_id: str,
    runtime_action: dict[str, Any] | None,
    transaction_runtime_report: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema": "v212_snapshot_display_transaction_integration_dark_state",
        "table": {
            "table_id": table_id,
            "slot_id": table_id,
            "slot_bbox": {"x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0},
            "action_event_id": f"evt_{frame_id}",
        },
        "frame_id": frame_id,
        "frame_name": frame_id,
        "hand_id": frame_id,
        "runtime_action": runtime_action if isinstance(runtime_action, dict) else {},
        "action_transaction_runtime": transaction_runtime_report if isinstance(transaction_runtime_report, dict) else {},
        "runtime_lifecycle": {
            "v212_audit": True,
            "transaction_runtime_report_present": isinstance(transaction_runtime_report, dict),
        },
        "errors": [],
        "warnings": [],
    }


def _prepare_clear_state(base_clear: dict[str, Any], *, frame_id: str, hand_id: str) -> dict[str, Any]:
    payload = copy.deepcopy(base_clear)
    old_frame_id = str(payload.get("frame_id") or "")
    old_hand_id = str(payload.get("hand_id") or "")

    def replace_strings(value: Any) -> Any:
        if isinstance(value, str):
            text = value
            if old_frame_id:
                text = text.replace(old_frame_id, frame_id)
            if old_hand_id:
                text = text.replace(old_hand_id, hand_id)
            return text
        if isinstance(value, list):
            return [replace_strings(item) for item in value]
        if isinstance(value, dict):
            return {key: replace_strings(item) for key, item in value.items()}
        return value

    payload = replace_strings(payload)
    payload["frame_id"] = frame_id
    # Clear_JSON schema forbids top-level hand_id/table technical fields.
    # hand_id is passed to save_dark_and_clear_table_frame_json(...) separately.
    payload.pop("hand_id", None)
    payload.pop("click_result", None)
    payload.pop("table", None)
    return payload


def _run_case(
    *,
    display_module: Any,
    gate_cls: Any,
    base_clear: dict[str, Any],
    name: str,
    action_status: str,
    expected_final_saved: bool,
    expected_contract_status: str,
    expected_contract_reason: str,
    expected_publication_stage: str,
    service_status: str = "skipped",
    open_transaction: bool = True,
    clear_json_state_machine: Any = None,
) -> dict[str, Any]:
    table_id = f"table_{name}"
    frame_id = f"{table_id}_v212_preflop"
    hand_id = f"{table_id}_hand_v212"
    clear_state = _prepare_clear_state(base_clear, frame_id=frame_id, hand_id=hand_id)

    gate = gate_cls(dry_run_counts_as_completed=True, release_on_inactive=True)

    if open_transaction:
        gate.begin_analysis_cycle(
            table_id=table_id,
            action_event_id=f"evt_{name}",
            action_signature=f"sig_{name}",
        )
        gate.begin_action_cycle(
            table_id=table_id,
            action_event_id=f"evt_{name}",
            action_signature=f"sig_{name}",
        )

    runtime_action = _runtime_action(
        service_status=service_status,
        action_status=action_status,
        decision_id=f"d_v212_{name}",
        dry_run=(action_status != "clicked"),
        real_click_enabled=(action_status == "clicked"),
        guard_passed=action_status in {"dry_run", "clicked", "confirmed"},
    )

    transaction_runtime_report = gate.finalize_from_runtime(
        table_id=table_id,
        runtime_action=runtime_action,
    )

    clear_json_save_allowed = bool(transaction_runtime_report.get("click_completed"))
    click_result = transaction_runtime_report.get("click_result")
    click_result_for_clear = click_result if isinstance(click_result, dict) and clear_json_save_allowed else None

    original_builder = display_module.build_clear_json_from_dark_state
    original_click_guard = display_module._build_click_execution_guard_report

    def _passing_click_guard_report(**kwargs):
        click_result_payload = kwargs.get("click_result")
        decision_id = ""
        if isinstance(click_result_payload, dict):
            decision_id = str(click_result_payload.get("decision_id") or "")
        return {
            "schema_version": "click_result_v09",
            "status": "dry_run",
            "reason": "v212_audit_click_guard_passed",
            "message": "V2.12 audit isolates transaction/save boundary; ClickExecutionGuard is forced to pass inside this tool only.",
            "guard_passed": True,
            "decision_id": decision_id,
            "dry_run": True,
            "real_click_enabled": False,
            "guards": {
                "v212_boundary_audit_override": True,
            },
            "source": "V2.12DisplayTransactionIntegrationAudit",
        }

    display_module.build_clear_json_from_dark_state = lambda state: copy.deepcopy(clear_state)
    display_module._build_click_execution_guard_report = _passing_click_guard_report
    try:
        dark_path, clear_path = display_module.save_dark_and_clear_table_frame_json(
            state=_make_dark_state(
                table_id=table_id,
                frame_id=frame_id,
                runtime_action=runtime_action,
                transaction_runtime_report=transaction_runtime_report,
            ),
            cycle_dir=OUT_DIR,
            table_id=table_id,
            hand_id=hand_id,
            frame_name=frame_id,
            active_confirmed=True,
            clear_json_state_machine=clear_json_state_machine,
            clear_json_save_allowed=clear_json_save_allowed,
            clear_json_build_allowed=True,
            clear_json_build_block_reason=None,
            click_result=click_result_for_clear,
        )
    finally:
        display_module.build_clear_json_from_dark_state = original_builder
        display_module._build_click_execution_guard_report = original_click_guard

    dark_state = _load_json(Path(dark_path))
    clear_contract = dark_state.get("clear_json_contract") if isinstance(dark_state.get("clear_json_contract"), dict) else {}
    saved_final = _load_json(Path(clear_path)) if clear_path and Path(clear_path).exists() else None

    final_saved = clear_path is not None and Path(clear_path).exists()
    saved_click_result = saved_final.get("click_result") if isinstance(saved_final, dict) else None

    checks = {
        "transaction_completion_matches_save_allowed": bool(transaction_runtime_report.get("click_completed")) == clear_json_save_allowed,
        "click_result_for_clear_available_matches_save_allowed": isinstance(click_result_for_clear, dict) == clear_json_save_allowed,
        "final_saved_expected": final_saved is expected_final_saved,
        "contract_status_expected": clear_contract.get("status") == expected_contract_status,
        "contract_reason_expected": clear_contract.get("reason") == expected_contract_reason,
        "publication_stage_expected": clear_contract.get("publication_stage") == expected_publication_stage,
        "dark_json_saved": Path(dark_path).exists(),
        "final_click_result_attached_only_when_saved": (
            saved_click_result == click_result_for_clear
            if expected_final_saved
            else saved_click_result is None
        ),
    }

    return {
        "scenario": name,
        "action_status": action_status,
        "service_status": service_status,
        "open_transaction": open_transaction,
        "transaction_runtime_report": transaction_runtime_report,
        "derived_display_inputs": {
            "clear_json_save_allowed": clear_json_save_allowed,
            "click_result_for_clear_available": isinstance(click_result_for_clear, dict),
            "click_result_for_clear": click_result_for_clear,
        },
        "dark_json": {
            "path": str(dark_path),
            "exists": Path(dark_path).exists(),
            "clear_json_contract": clear_contract,
        },
        "final_clear_json": {
            "path": str(clear_path) if clear_path else None,
            "exists": final_saved,
            "saved_frame_id": saved_final.get("frame_id") if isinstance(saved_final, dict) else None,
            "saved_click_result": saved_click_result,
        },
        "expected": {
            "final_saved": expected_final_saved,
            "contract_status": expected_contract_status,
            "contract_reason": expected_contract_reason,
            "publication_stage": expected_publication_stage,
        },
        "checks": checks,
        "ok": all(checks.values()),
    }


def _run_not_active_case(*, display_module: Any, base_clear: dict[str, Any]) -> dict[str, Any]:
    table_id = "table_v212_not_active"
    frame_id = "table_v212_not_active_frame"
    dark_state = _make_dark_state(
        table_id=table_id,
        frame_id=frame_id,
        runtime_action=None,
        transaction_runtime_report=None,
    )

    dark_path, clear_path = display_module.save_dark_and_clear_table_frame_json(
        state=dark_state,
        cycle_dir=OUT_DIR,
        table_id=table_id,
        hand_id="hand_v212_not_active",
        frame_name=frame_id,
        active_confirmed=False,
        clear_json_state_machine=None,
        clear_json_save_allowed=True,
        clear_json_build_allowed=True,
        clear_json_build_block_reason=None,
        click_result=None,
    )

    saved_dark = _load_json(Path(dark_path))
    contract = saved_dark.get("clear_json_contract") if isinstance(saved_dark.get("clear_json_contract"), dict) else {}

    checks = {
        "dark_json_saved": Path(dark_path).exists(),
        "final_not_saved": clear_path is None,
        "status_skipped": contract.get("status") == "skipped",
        "reason_not_active": contract.get("reason") == "not_active_poker_state",
        "publication_stage_dark_only": contract.get("publication_stage") == "dark_json_only",
    }

    return {
        "scenario": "not_active_dark_json_only",
        "dark_json": {"path": str(dark_path), "exists": Path(dark_path).exists(), "clear_json_contract": contract},
        "final_clear_json": {"path": None, "exists": False},
        "checks": checks,
        "ok": all(checks.values()),
    }


def _run_hard_stop_case(*, display_module: Any) -> dict[str, Any]:
    table_id = "table_v212_hard_stop"
    frame_id = "table_v212_hard_stop_frame"
    dark_state = _make_dark_state(
        table_id=table_id,
        frame_id=frame_id,
        runtime_action=None,
        transaction_runtime_report=None,
    )

    dark_path, clear_path = display_module.save_dark_and_clear_table_frame_json(
        state=dark_state,
        cycle_dir=OUT_DIR,
        table_id=table_id,
        hand_id="hand_v212_hard_stop",
        frame_name=frame_id,
        active_confirmed=True,
        clear_json_state_machine=None,
        clear_json_save_allowed=True,
        clear_json_build_allowed=False,
        clear_json_build_block_reason="duplicate_active_frame_blocked",
        click_result=None,
    )

    saved_dark = _load_json(Path(dark_path))
    contract = saved_dark.get("clear_json_contract") if isinstance(saved_dark.get("clear_json_contract"), dict) else {}

    checks = {
        "dark_json_saved": Path(dark_path).exists(),
        "final_not_saved": clear_path is None,
        "status_skipped": contract.get("status") == "skipped",
        "reason_duplicate": contract.get("reason") == "duplicate_active_frame_blocked",
        "publication_stage_dark_only": contract.get("publication_stage") == "dark_json_only",
        "hard_stop_true": contract.get("hard_stop_before_pending_decision") is True,
    }

    return {
        "scenario": "hard_stop_before_pending_decision",
        "dark_json": {"path": str(dark_path), "exists": Path(dark_path).exists(), "clear_json_contract": contract},
        "final_clear_json": {"path": None, "exists": False},
        "checks": checks,
        "ok": all(checks.values()),
    }


def main() -> int:
    if not DISPLAY_FILE.exists():
        raise FileNotFoundError(DISPLAY_FILE)
    if not GATE_PATH.exists():
        raise FileNotFoundError(GATE_PATH)

    _clean_output_dir()

    os.environ["POKERVISION_SOLVER_PREFLOP_ROOT"] = str(PROJECT_ROOT)
    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))

    display_module = _load_module("v212_display_analysis_cycle", DISPLAY_FILE)
    gate_module = _load_module("v212_table_action_transaction_gate", GATE_PATH)
    gate_cls = gate_module.TableActionTransactionGate

    pending_path = _discover_one_preflop_file()
    base_clear = _load_json(pending_path)

    display_text = DISPLAY_FILE.read_text(encoding="utf-8")
    static_checks = {
        "save_boundary_present": "def save_dark_and_clear_table_frame_json(" in display_text,
        "build_from_dark_state_present": "clear_state_candidate = build_clear_json_from_dark_state(state)" in display_text,
        "save_allowed_blocker_present": "elif not clear_json_save_allowed:" in display_text,
        "missing_click_result_blocker_present": "missing_click_result_for_final_clear_json" in display_text,
        "final_save_present": "save_clear_table_frame_json(" in display_text,
        "caller_passes_save_allowed": "clear_json_save_allowed=clear_json_save_allowed" in display_text,
        "caller_passes_click_result": "click_result=click_result_for_clear" in display_text,
    }

    scenarios = [
        _run_case(
            display_module=display_module,
            gate_cls=gate_cls,
            base_clear=base_clear,
            name="dry_run_completed_final_saved",
            action_status="dry_run",
            expected_final_saved=True,
            expected_contract_status="saved",
            expected_contract_reason="state_machine_not_provided",
            expected_publication_stage="final",
        ),
        _run_case(
            display_module=display_module,
            gate_cls=gate_cls,
            base_clear=base_clear,
            name="clicked_completed_final_saved",
            action_status="clicked",
            expected_final_saved=True,
            expected_contract_status="saved",
            expected_contract_reason="state_machine_not_provided",
            expected_publication_stage="final",
        ),
        _run_case(
            display_module=display_module,
            gate_cls=gate_cls,
            base_clear=base_clear,
            name="skipped_runtime_pending_only",
            action_status="skipped",
            expected_final_saved=False,
            expected_contract_status="skipped",
            expected_contract_reason="action_transaction_not_completed",
            expected_publication_stage="pending_only",
        ),
        _run_case(
            display_module=display_module,
            gate_cls=gate_cls,
            base_clear=base_clear,
            name="blocked_runtime_pending_only",
            action_status="blocked",
            expected_final_saved=False,
            expected_contract_status="skipped",
            expected_contract_reason="action_transaction_not_completed",
            expected_publication_stage="pending_only",
        ),
        _run_not_active_case(display_module=display_module, base_clear=base_clear),
        _run_hard_stop_case(display_module=display_module),
    ]

    ok_count = len([item for item in scenarios if item["ok"] is True])
    bad_count = len(scenarios) - ok_count

    final_files = sorted(str(path) for path in OUT_DIR.rglob("Clear_JSON/**/*.json"))
    pending_files = sorted(str(path) for path in OUT_DIR.rglob("Clear_JSON_Pending/**/*.json"))
    dark_files = sorted(str(path) for path in OUT_DIR.rglob("Dark_JSON/**/*.json"))

    output_checks = {
        "dark_json_for_each_scenario": len(dark_files) == len(scenarios),
        "final_clear_only_for_completed_cases": len(final_files) == 2,
        "pending_clear_for_active_build_cases": len(pending_files) == 4,
    }

    report = {
        "schema": "pokervision_solver_preflop_v212_snapshot_display_transaction_integration_audit_v1",
        "status": "ok" if all(static_checks.values()) and all(output_checks.values()) and bad_count == 0 else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_display": str(DISPLAY_FILE),
        "snapshot_gate": str(GATE_PATH),
        "pending_template": str(pending_path),
        "out_dir": str(OUT_DIR),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "static_checks": static_checks,
        "output_checks": output_checks,
        "scenario_count": len(scenarios),
        "ok_count": ok_count,
        "bad_count": bad_count,
        "dark_files_count": len(dark_files),
        "pending_files_count": len(pending_files),
        "final_files_count": len(final_files),
        "scenarios": scenarios,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
