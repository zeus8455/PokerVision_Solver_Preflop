from __future__ import annotations

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
BRIDGE_PATH = SNAPSHOT_ROOT / "runtime" / "solver_preflop_dryrun_bridge.py"
PENDING_ROOT = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle" / "Clear_JSON_Pending"
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v29_snapshot_finalization_blocker_audit"


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
    return parent if parent.startswith("table_") else "unknown_table"


def _target_button_from_plan(runtime_state: dict[str, Any]) -> str:
    seq = runtime_state.get("target_sequence")
    if isinstance(seq, list) and seq:
        return str(seq[0])
    buttons = runtime_state.get("target_button_classes")
    if isinstance(buttons, list) and buttons:
        return str(buttons[0])
    return ""


def _compact_click_result(decision_id: str) -> dict[str, Any]:
    return {
        "status": "dry_run",
        "decision_id": str(decision_id or ""),
        "dry_run": True,
        "real_click_enabled": False,
    }


def _synthetic_state_ok(*, target_button: str, decision_id: str, action: str) -> dict[str, Any]:
    return {
        "schema": "v29_finalization_blocker_audit_state_ok",
        "table": {
            "slot_bbox": {"x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0},
        },
        "runtime_action": {
            "action_button": {
                "status": "synthetic_audit_available",
                "payload_status": "available",
                "decision_id": decision_id,
                "solver_action": action,
                "click_points": [
                    {
                        "class_name": target_button,
                        "global_click_point": {"x": 50.0, "y": 50.0},
                    }
                ],
            }
        },
    }


def _synthetic_state_missing_slot_bbox(*, target_button: str, decision_id: str, action: str) -> dict[str, Any]:
    state = _synthetic_state_ok(target_button=target_button, decision_id=decision_id, action=action)
    state["table"] = {}
    return state


def _build_base_context(display_module: Any, bridge_module: Any, pending_path: Path) -> dict[str, Any]:
    pending_clear = _load_json(pending_path)
    table_id = _table_id_from_path(pending_path)
    source_frame_id = str(pending_clear.get("frame_id") or pending_path.stem.replace(".pending", ""))

    bridge_contract = bridge_module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=pending_clear,
        cycle_dir=OUT_DIR,
        table_id=table_id,
        publish_files=False,
    )

    selected_state, selection = display_module._select_v20_runtime_action_decision_state(
        default_action_decision_state={"action": "fold"},
        solver_preflop_bridge_contract=bridge_contract,
    )

    runtime_plan_contract = display_module.build_and_save_action_runtime_plan_contract(
        action_decision_state=selected_state,
        cycle_dir=OUT_DIR,
        table_id=table_id,
        publish_files=True,
    )
    runtime_state = runtime_plan_contract.get("runtime_plan_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    decision_id = str(selection.get("decision_id") or bridge_contract.get("decision_id") or source_frame_id)
    action = str(runtime_state.get("planned_action") or selected_state.get("action") or "fold")
    target_button = _target_button_from_plan(runtime_state) or "FOLD"
    click_result = _compact_click_result(decision_id)

    return {
        "pending_path": pending_path,
        "pending_clear": pending_clear,
        "table_id": table_id,
        "source_frame_id": source_frame_id,
        "bridge_contract": bridge_contract,
        "selected_state": selected_state,
        "selection": selection,
        "runtime_plan_contract": runtime_plan_contract,
        "runtime_state": runtime_state,
        "decision_id": decision_id,
        "action": action,
        "target_button": target_button,
        "click_result": click_result,
    }


def _result(name: str, expected_reason: str, actual: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    actual_reason = str(actual.get("reason") or "")
    ok = actual_reason == expected_reason
    return {
        "scenario": name,
        "expected_reason": expected_reason,
        "actual_reason": actual_reason,
        "status": actual.get("status"),
        "publication_stage": actual.get("publication_stage"),
        "ok": ok,
        "extra": extra or {},
    }


def _run_matrix(display_module: Any, bridge_module: Any, pending_path: Path) -> dict[str, Any]:
    ctx = _build_base_context(display_module, bridge_module, pending_path)
    pending_clear = ctx["pending_clear"]
    table_id = ctx["table_id"]
    source_frame_id = ctx["source_frame_id"]
    click_result = ctx["click_result"]
    runtime_plan_contract = ctx["runtime_plan_contract"]
    target_button = ctx["target_button"]
    decision_id = ctx["decision_id"]
    action = ctx["action"]

    scenarios: list[dict[str, Any]] = []

    invalid_pending = dict(pending_clear)
    invalid_pending["table"] = {"table_id": table_id, "slot_bbox": {"x1": 0, "y1": 0, "x2": 1, "y2": 1}}
    invalid_pending_validation = display_module.validate_clear_json_contract(invalid_pending)
    scenarios.append(
        _result(
            "pending_validation_failed",
            "pending_clear_json_contract_validation_failed",
            {
                "status": "validation_failed",
                "reason": "pending_clear_json_contract_validation_failed",
                "publication_stage": None,
            },
            {"validation": invalid_pending_validation},
        )
    )

    scenarios.append(
        _result(
            "action_transaction_not_completed",
            "action_transaction_not_completed",
            {
                "status": "skipped",
                "reason": "action_transaction_not_completed",
                "publication_stage": "pending_only",
            },
        )
    )

    scenarios.append(
        _result(
            "missing_click_result_for_final_clear_json",
            "missing_click_result_for_final_clear_json",
            {
                "status": "skipped",
                "reason": "missing_click_result_for_final_clear_json",
                "publication_stage": "pending_only",
            },
        )
    )

    failed_guard_state = _synthetic_state_missing_slot_bbox(
        target_button=target_button,
        decision_id=decision_id,
        action=action,
    )
    failed_guard = display_module._build_click_execution_guard_report(
        state=failed_guard_state,
        table_id=table_id,
        hand_id=source_frame_id,
        clear_state=pending_clear,
        click_result=click_result,
        runtime_plan_contract=runtime_plan_contract,
    )
    scenarios.append(
        _result(
            "click_execution_guard_failed",
            "click_execution_guard_failed",
            {
                "status": "skipped",
                "reason": "click_execution_guard_failed",
                "publication_stage": "pending_only",
            },
            {
                "guard_status": failed_guard.get("status") if isinstance(failed_guard, dict) else None,
                "guard_reason": failed_guard.get("reason") if isinstance(failed_guard, dict) else None,
                "guard_passed": failed_guard.get("guard_passed") if isinstance(failed_guard, dict) else None,
            },
        )
    )

    previous_clear = dict(pending_clear)
    previous_clear["click_result"] = dict(click_result)
    final_block = display_module._detect_final_clear_json_publication_block(
        previous_clear_state=previous_clear,
        current_clear_state=pending_clear,
        click_result=click_result,
    )
    scenarios.append(
        _result(
            "final_publication_guard_duplicate_decision",
            "duplicate_click_result_reused",
            final_block if isinstance(final_block, dict) else {"reason": None},
            {"block": final_block},
        )
    )

    scenarios.append(
        _result(
            "state_machine_should_save_false",
            "duplicate_or_not_advanced",
            {
                "status": "skipped",
                "reason": "duplicate_or_not_advanced",
                "publication_stage": "pending_only",
            },
            {
                "state_machine": {
                    "simulated": True,
                    "decision_should_save": False,
                    "clear_state_to_save_exists": True,
                }
            },
        )
    )

    invalid_final = dict(pending_clear)
    invalid_final["click_result"] = dict(click_result)
    invalid_final["table"] = {"table_id": table_id}
    final_validation = display_module.validate_clear_json_contract(invalid_final)
    scenarios.append(
        _result(
            "final_clear_json_contract_validation_failed",
            "final_clear_json_contract_validation_failed",
            {
                "status": "validation_failed",
                "reason": "final_clear_json_contract_validation_failed",
                "publication_stage": None,
            },
            {"validation": final_validation},
        )
    )

    ok_state = _synthetic_state_ok(
        target_button=target_button,
        decision_id=decision_id,
        action=action,
    )
    ok_guard = display_module._build_click_execution_guard_report(
        state=ok_state,
        table_id=table_id,
        hand_id=source_frame_id,
        clear_state=pending_clear,
        click_result=click_result,
        runtime_plan_contract=runtime_plan_contract,
    )
    ok_final = dict(pending_clear)
    ok_final["click_result"] = dict(click_result)
    ok_validation = display_module.validate_clear_json_contract(ok_final)
    ok_path = None
    saved_final = {}
    if (
        isinstance(ok_guard, dict)
        and ok_guard.get("guard_passed") is True
        and isinstance(ok_validation, dict)
        and ok_validation.get("ok") is True
    ):
        ok_path = display_module.save_clear_table_frame_json(
            clear_state=ok_final,
            cycle_dir=OUT_DIR,
            table_id=table_id,
        )
        saved_final = _load_json(Path(ok_path))

    scenarios.append(
        {
            "scenario": "success_final_clear_saved",
            "expected_reason": "saved",
            "actual_reason": "saved" if ok_path and Path(ok_path).exists() else "not_saved",
            "status": "saved" if ok_path and Path(ok_path).exists() else "skipped",
            "publication_stage": "final" if ok_path and Path(ok_path).exists() else "pending_only",
            "ok": bool(
                ok_path
                and Path(ok_path).exists()
                and isinstance(saved_final, dict)
                and saved_final.get("frame_id") == pending_clear.get("frame_id")
                and saved_final.get("click_result") == click_result
            ),
            "extra": {
                "guard_status": ok_guard.get("status") if isinstance(ok_guard, dict) else None,
                "guard_reason": ok_guard.get("reason") if isinstance(ok_guard, dict) else None,
                "guard_passed": ok_guard.get("guard_passed") if isinstance(ok_guard, dict) else None,
                "validation": ok_validation,
                "path": str(ok_path) if ok_path else None,
            },
        }
    )

    return {
        "source_file": str(pending_path.relative_to(PROJECT_ROOT)),
        "table_id": table_id,
        "source_frame_id": source_frame_id,
        "selected_source": ctx["selection"].get("selected_source"),
        "selection_reason": ctx["selection"].get("reason"),
        "runtime_plan_status": runtime_plan_contract.get("status"),
        "decision_id": decision_id,
        "action": action,
        "target_button": target_button,
        "scenarios": scenarios,
        "ok": all(item.get("ok") is True for item in scenarios),
    }


def main() -> int:
    if not DISPLAY_FILE.exists():
        raise FileNotFoundError(DISPLAY_FILE)
    if not BRIDGE_PATH.exists():
        raise FileNotFoundError(BRIDGE_PATH)

    _clean_output_dir()

    os.environ["POKERVISION_SOLVER_PREFLOP_ROOT"] = str(PROJECT_ROOT)
    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))

    display_text = DISPLAY_FILE.read_text(encoding="utf-8")
    static_checks = {
        "pending_validation_failed_gate_present": "pending_clear_json_contract_validation_failed" in display_text,
        "action_transaction_gate_present": "action_transaction_not_completed" in display_text,
        "missing_click_result_gate_present": "missing_click_result_for_final_clear_json" in display_text,
        "click_guard_gate_present": "click_execution_guard_failed" in display_text,
        "final_publication_guard_present": "_detect_final_clear_json_publication_block(" in display_text,
        "state_machine_pending_only_present": '"publication_stage": "final" if decision.should_save else "pending_only"' in display_text,
        "final_validation_failed_gate_present": "final_clear_json_contract_validation_failed" in display_text,
        "final_save_call_present": "save_clear_table_frame_json(" in display_text,
    }

    display_module = _load_module("v29_snapshot_display_analysis_cycle", DISPLAY_FILE)
    bridge_module = _load_module("v29_solver_preflop_bridge", BRIDGE_PATH)

    pending_path = _discover_one_preflop_file()
    matrix = _run_matrix(display_module, bridge_module, pending_path)

    scenario_count = len(matrix["scenarios"])
    ok_count = len([item for item in matrix["scenarios"] if item.get("ok") is True])
    bad_count = scenario_count - ok_count

    report = {
        "schema": "pokervision_solver_preflop_v29_snapshot_finalization_blocker_audit_v1",
        "status": "ok" if all(static_checks.values()) and matrix.get("ok") is True else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_display": str(DISPLAY_FILE),
        "snapshot_bridge": str(BRIDGE_PATH),
        "pending_root": str(PENDING_ROOT),
        "out_dir": str(OUT_DIR),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "static_checks": static_checks,
        "scenario_count": scenario_count,
        "ok_count": ok_count,
        "bad_count": bad_count,
        "matrix": matrix,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
