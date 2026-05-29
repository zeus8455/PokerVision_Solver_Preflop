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
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v27_snapshot_display_finalization_audit"


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


def _discover_pending_preflop_files() -> list[Path]:
    if not PENDING_ROOT.exists():
        return []
    return sorted(PENDING_ROOT.glob("table_*/*preflop*.json"))


def _table_id_from_path(path: Path) -> str:
    parent = path.parent.name
    return parent if parent.startswith("table_") else "unknown_table"


def _clean_output_dir() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _target_button_from_plan(runtime_state: dict[str, Any]) -> str:
    seq = runtime_state.get("target_sequence")
    if isinstance(seq, list) and seq:
        return str(seq[0])
    buttons = runtime_state.get("target_button_classes")
    if isinstance(buttons, list) and buttons:
        return str(buttons[0])
    return ""


def _build_compact_click_result(*, decision_id: str) -> dict[str, Any]:
    return {
        "status": "dry_run",
        "decision_id": str(decision_id or ""),
        "dry_run": True,
        "real_click_enabled": False,
    }


def _build_synthetic_dark_state(
    *,
    pending_clear: dict[str, Any],
    target_button: str,
    decision_id: str,
    action: str,
) -> dict[str, Any]:
    table = dict(pending_clear.get("table")) if isinstance(pending_clear.get("table"), dict) else {}
    table["slot_bbox"] = {
        "x1": 0.0,
        "y1": 0.0,
        "x2": 100.0,
        "y2": 100.0,
    }

    return {
        "schema": "v27_snapshot_display_finalization_audit_dark_state",
        "table": table,
        "runtime_action": {
            "action_button": {
                "status": "synthetic_audit_available",
                "payload_status": "available",
                "decision_id": decision_id,
                "solver_action": action,
                "click_points": [
                    {
                        "class_name": target_button,
                        "global_click_point": {
                            "x": 50.0,
                            "y": 50.0,
                        },
                    }
                ],
            }
        },
    }


def _run_one(display_module: Any, bridge_module: Any, path: Path) -> dict[str, Any]:
    pending_clear = _load_json(path)
    table_id = _table_id_from_path(path)
    source_frame_id = str(pending_clear.get("frame_id") or path.stem)

    pending_validation = display_module.validate_clear_json_contract(pending_clear)

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

    pending_runtime_plan_contract = display_module.build_and_save_action_runtime_plan_contract(
        action_decision_state=selected_state,
        cycle_dir=OUT_DIR,
        table_id=table_id,
        publish_files=False,
    )
    pending_runtime_state = pending_runtime_plan_contract.get("runtime_plan_state")
    if not isinstance(pending_runtime_state, dict):
        pending_runtime_state = {}

    final_runtime_plan_contract = display_module.build_and_save_action_runtime_plan_contract(
        action_decision_state=selected_state,
        cycle_dir=OUT_DIR,
        table_id=table_id,
        publish_files=True,
    )
    final_runtime_state = final_runtime_plan_contract.get("runtime_plan_state")
    if not isinstance(final_runtime_state, dict):
        final_runtime_state = {}

    decision_id = str(
        selection.get("decision_id")
        or bridge_contract.get("decision_id")
        or source_frame_id
    )
    action = str(
        final_runtime_state.get("planned_action")
        or pending_runtime_state.get("planned_action")
        or selected_state.get("action")
        or ""
    )
    target_button = _target_button_from_plan(final_runtime_state) or _target_button_from_plan(pending_runtime_state)

    compact_click_result = _build_compact_click_result(decision_id=decision_id)

    synthetic_state = _build_synthetic_dark_state(
        pending_clear=pending_clear,
        target_button=target_button,
        decision_id=decision_id,
        action=action,
    )

    click_execution_guard_report = display_module._build_click_execution_guard_report(
        state=synthetic_state,
        table_id=table_id,
        hand_id=source_frame_id,
        clear_state=pending_clear,
        click_result=compact_click_result,
        runtime_plan_contract=final_runtime_plan_contract,
    )

    final_publication_block = display_module._detect_final_clear_json_publication_block(
        previous_clear_state=None,
        current_clear_state=pending_clear,
        click_result=compact_click_result,
    )

    branch_audit = {
        "pending_validation_ok": bool(isinstance(pending_validation, dict) and pending_validation.get("ok")),
        "clear_json_save_allowed_if_transaction_completed": True,
        "click_result_received": isinstance(compact_click_result, dict),
        "click_result_fields": sorted(compact_click_result.keys()),
        "click_execution_guard_called": True,
        "click_execution_guard_passed": bool(
            isinstance(click_execution_guard_report, dict)
            and click_execution_guard_report.get("guard_passed") is True
        ),
        "final_publication_blocked": isinstance(final_publication_block, dict),
        "final_publication_block": final_publication_block,
        "state_machine_simulation": {
            "mode": "single_frame_should_save_true",
            "decision_should_save": True,
            "clear_state_to_save_exists": True,
        },
    }

    final_clear = dict(pending_clear)
    final_clear["click_result"] = dict(compact_click_result)
    final_validation = display_module.validate_clear_json_contract(final_clear)

    final_clear_path = None
    saved_final = {}
    if (
        branch_audit["pending_validation_ok"]
        and branch_audit["click_result_received"]
        and branch_audit["click_execution_guard_passed"]
        and not branch_audit["final_publication_blocked"]
        and isinstance(final_validation, dict)
        and final_validation.get("ok")
    ):
        final_clear_path = display_module.save_clear_table_frame_json(
            clear_state=final_clear,
            cycle_dir=OUT_DIR,
            table_id=table_id,
        )
        saved_final = _load_json(Path(final_clear_path))

    saved_click = saved_final.get("click_result") if isinstance(saved_final, dict) else None

    checks = {
        "solver_source_selected": selection.get("selected_source") == "Solver_Preflop_Bridge",
        "pending_runtime_preview_expected": pending_runtime_plan_contract.get("status") == "preview_not_saved_pending_only",
        "final_runtime_plan_saved": final_runtime_plan_contract.get("status") == "saved",
        "click_execution_guard_passed": branch_audit["click_execution_guard_passed"],
        "compact_click_result_schema_safe": set(compact_click_result.keys()) == {
            "status",
            "decision_id",
            "dry_run",
            "real_click_enabled",
        },
        "final_validation_ok": bool(isinstance(final_validation, dict) and final_validation.get("ok")),
        "final_clear_saved": bool(final_clear_path and Path(final_clear_path).exists()),
        "saved_final_contains_same_click_result": saved_click == compact_click_result,
    }

    return {
        "file": str(path.relative_to(PROJECT_ROOT)),
        "table_id": table_id,
        "source_frame_id": source_frame_id,
        "selected_source": selection.get("selected_source"),
        "selection_reason": selection.get("reason"),
        "decision_id": decision_id,
        "action": action,
        "target_button": target_button,
        "bridge": {
            "status": bridge_contract.get("status"),
            "source_frame_id": bridge_contract.get("source_frame_id"),
            "decision_id": bridge_contract.get("decision_id"),
        },
        "pending_runtime_plan": {
            "status": pending_runtime_plan_contract.get("status"),
            "publication_stage": pending_runtime_plan_contract.get("publication_stage"),
            "file_publication_enabled": pending_runtime_plan_contract.get("file_publication_enabled"),
            "path": pending_runtime_plan_contract.get("path"),
        },
        "final_runtime_plan": {
            "status": final_runtime_plan_contract.get("status"),
            "publication_stage": final_runtime_plan_contract.get("publication_stage"),
            "file_publication_enabled": final_runtime_plan_contract.get("file_publication_enabled"),
            "path": final_runtime_plan_contract.get("path"),
        },
        "central_finalization_audit": branch_audit,
        "click_execution_guard": {
            "status": click_execution_guard_report.get("status") if isinstance(click_execution_guard_report, dict) else None,
            "reason": click_execution_guard_report.get("reason") if isinstance(click_execution_guard_report, dict) else None,
            "guard_passed": click_execution_guard_report.get("guard_passed") if isinstance(click_execution_guard_report, dict) else None,
            "message": click_execution_guard_report.get("message") if isinstance(click_execution_guard_report, dict) else None,
        },
        "compact_click_result": compact_click_result,
        "final_clear": {
            "validation": final_validation,
            "path": str(final_clear_path) if final_clear_path else None,
            "exists": bool(final_clear_path and Path(final_clear_path).exists()),
            "saved_click_result": saved_click,
        },
        "checks": checks,
        "ok": all(checks.values()),
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
        "solver_source_enabled": "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = True" in display_text,
        "dry_run_only": "V20_SOLVER_PREFLOP_DRY_RUN_ONLY = True" in display_text,
        "pending_preview_status_present": "preview_not_saved_pending_only" in display_text,
        "central_action_transaction_gate_present": "action_transaction_not_completed" in display_text,
        "central_missing_click_result_gate_present": "missing_click_result_for_final_clear_json" in display_text,
        "central_click_guard_gate_present": "click_execution_guard_failed" in display_text,
        "central_final_publication_guard_present": "_detect_final_clear_json_publication_block(" in display_text,
    }

    display_module = _load_module("v27_snapshot_display_analysis_cycle", DISPLAY_FILE)
    bridge_module = _load_module("v27_solver_preflop_bridge", BRIDGE_PATH)

    files = _discover_pending_preflop_files()
    results = [_run_one(display_module, bridge_module, path) for path in files]

    ok_results = [item for item in results if item.get("ok") is True]
    bad_results = [item for item in results if item.get("ok") is not True]

    runtime_files = sorted(str(path) for path in OUT_DIR.rglob("Action_Runtime_Plan_JSON/**/*.json"))
    final_files = sorted(str(path) for path in OUT_DIR.rglob("Clear_JSON/**/*.json"))

    report = {
        "schema": "pokervision_solver_preflop_v27_snapshot_display_finalization_audit_v1",
        "status": "ok" if all(static_checks.values()) and files and not bad_results else "error",
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
        "files_total": len(files),
        "ok_count": len(ok_results),
        "bad_count": len(bad_results),
        "published_runtime_files_count": len(runtime_files),
        "published_final_clear_files_count": len(final_files),
        "published_runtime_files": runtime_files,
        "published_final_clear_files": final_files,
        "results": results,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
