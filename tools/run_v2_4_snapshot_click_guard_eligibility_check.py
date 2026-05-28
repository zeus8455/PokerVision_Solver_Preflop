from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DISPLAY_FILE = SNAPSHOT_ROOT / "display_analysis_cycle.py"
BRIDGE_PATH = SNAPSHOT_ROOT / "runtime" / "solver_preflop_dryrun_bridge.py"
CLICK_GUARD_PATH = SNAPSHOT_ROOT / "logic" / "click_execution_guard.py"
PENDING_ROOT = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle" / "Clear_JSON_Pending"
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v24_snapshot_click_guard_eligibility"


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


def _target_button_from_plan(runtime_state: dict[str, Any]) -> str:
    seq = runtime_state.get("target_sequence")
    if isinstance(seq, list) and seq:
        return str(seq[0])
    buttons = runtime_state.get("target_button_classes")
    if isinstance(buttons, list) and buttons:
        return str(buttons[0])
    return ""


def _run_one(display_module: Any, bridge_module: Any, guard_module: Any, path: Path) -> dict[str, Any]:
    clear_state = _load_json(path)
    table_id = _table_id_from_path(path)

    bridge_contract = bridge_module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=clear_state,
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
        publish_files=False,
    )
    runtime_state = runtime_plan_contract.get("runtime_plan_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    target_button = _target_button_from_plan(runtime_state)
    action = str(runtime_state.get("planned_action") or selected_state.get("action") or "")
    decision_id = str(selection.get("decision_id") or bridge_contract.get("decision_id") or bridge_contract.get("source_frame_id") or "")

    dry_request = guard_module.ClickExecutionRequest(
        table_id=table_id,
        hand_id=str(bridge_contract.get("source_frame_id") or ""),
        street="preflop",
        decision_id=decision_id,
        action=action,
        target_button_class=target_button,
        click_point=(50.0, 50.0),
        slot_bbox=(0.0, 0.0, 100.0, 100.0),
        action_runtime_plan=runtime_state,
        already_executed_decision_ids=tuple(),
        dry_run=True,
        real_click_enabled=False,
    )
    dry_result = guard_module.validate_click_execution_request(
        dry_request,
        guard_module.ClickGuardConfig(),
    )

    repeated_request = guard_module.ClickExecutionRequest(
        table_id=table_id,
        hand_id=str(bridge_contract.get("source_frame_id") or ""),
        street="preflop",
        decision_id=decision_id,
        action=action,
        target_button_class=target_button,
        click_point=(50.0, 50.0),
        slot_bbox=(0.0, 0.0, 100.0, 100.0),
        action_runtime_plan=runtime_state,
        already_executed_decision_ids=(decision_id,),
        dry_run=True,
        real_click_enabled=False,
    )
    repeated_result = guard_module.validate_click_execution_request(
        repeated_request,
        guard_module.ClickGuardConfig(),
    )

    real_request = guard_module.ClickExecutionRequest(
        table_id=table_id,
        hand_id=str(bridge_contract.get("source_frame_id") or ""),
        street="preflop",
        decision_id=decision_id,
        action=action,
        target_button_class=target_button,
        click_point=(50.0, 50.0),
        slot_bbox=(0.0, 0.0, 100.0, 100.0),
        action_runtime_plan=runtime_state,
        already_executed_decision_ids=tuple(),
        dry_run=False,
        real_click_enabled=True,
    )
    real_result = guard_module.validate_click_execution_request(
        real_request,
        guard_module.ClickGuardConfig(
            real_click_master_armed=False,
            live_data_capture_no_click_mode=True,
            action_real_click_enabled=False,
            action_dry_run=True,
        ),
    )

    dry_guards = dry_result.get("guards") if isinstance(dry_result, dict) else {}
    dry_ok = (
        dry_result.get("status") == "dry_run"
        and dry_result.get("guard_passed") is True
        and dry_result.get("reason") == "all_click_execution_guards_passed"
        and dry_result.get("dry_run") is True
        and dry_result.get("real_click_enabled") is False
        and isinstance(dry_guards, dict)
        and dry_guards.get("plan_source_guard") is True
        and dry_guards.get("button_availability_guard") is True
        and dry_guards.get("slot_boundary_guard") is True
        and dry_guards.get("no_repeat_decision_guard") is True
        and dry_guards.get("real_click_master_guard") is True
        and dry_guards.get("live_no_click_guard") is True
        and dry_guards.get("dry_run_guard") is True
    )

    repeated_ok = (
        repeated_result.get("status") == "blocked"
        and repeated_result.get("reason") == "decision_id_already_executed"
        and repeated_result.get("guard_passed") is False
    )

    real_block_ok = (
        real_result.get("status") == "blocked"
        and real_result.get("reason") == "real_click_master_not_armed"
        and real_result.get("guard_passed") is False
        and real_result.get("real_click_enabled") is True
        and real_result.get("dry_run") is False
    )

    runtime_ok = bool(
        runtime_plan_contract.get("status") == "preview_not_saved_pending_only"
        and runtime_state.get("status") == "ok"
        and runtime_state.get("dry_run") is True
        and runtime_state.get("real_click_enabled") is False
        and bool(target_button)
    )

    return {
        "file": str(path.relative_to(PROJECT_ROOT)),
        "table_id": table_id,
        "source_frame_id": bridge_contract.get("source_frame_id"),
        "bridge_status": bridge_contract.get("status"),
        "selected_source": selection.get("selected_source"),
        "selection_reason": selection.get("reason"),
        "decision_id": decision_id,
        "action": action,
        "target_button": target_button,
        "runtime_plan": {
            "status": runtime_plan_contract.get("status"),
            "runtime_state_status": runtime_state.get("status"),
            "planned_action": runtime_state.get("planned_action"),
            "target_sequence": runtime_state.get("target_sequence"),
            "target_sequences": runtime_state.get("target_sequences"),
            "dry_run": runtime_state.get("dry_run"),
            "real_click_enabled": runtime_state.get("real_click_enabled"),
            "source": runtime_state.get("source"),
            "schema_version": runtime_state.get("schema_version"),
        },
        "dry_run_click_result": dry_result,
        "repeated_click_result": repeated_result,
        "forced_real_click_result": real_result,
        "checks": {
            "runtime_ok": runtime_ok,
            "dry_run_guard_ok": dry_ok,
            "repeat_guard_ok": repeated_ok,
            "real_click_block_ok": real_block_ok,
        },
        "ok": bool(runtime_ok and dry_ok and repeated_ok and real_block_ok),
    }


def main() -> int:
    if not DISPLAY_FILE.exists():
        raise FileNotFoundError(DISPLAY_FILE)
    if not BRIDGE_PATH.exists():
        raise FileNotFoundError(BRIDGE_PATH)
    if not CLICK_GUARD_PATH.exists():
        raise FileNotFoundError(CLICK_GUARD_PATH)

    os.environ["POKERVISION_SOLVER_PREFLOP_ROOT"] = str(PROJECT_ROOT)
    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))

    display_text = DISPLAY_FILE.read_text(encoding="utf-8")
    static_checks = {
        "solver_source_enabled": "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = True" in display_text,
        "dry_run_only": "V20_SOLVER_PREFLOP_DRY_RUN_ONLY = True" in display_text,
        "adapter_present": "def _adapt_v21_solver_preflop_action_decision_to_v06(" in display_text,
        "legacy_stub_compat": '"solver_stub_legacy_compat": True' in display_text,
    }

    display_module = _load_module("v24_snapshot_display_analysis_cycle", DISPLAY_FILE)
    bridge_module = _load_module("v24_solver_preflop_bridge", BRIDGE_PATH)
    guard_module = _load_module("v24_click_execution_guard", CLICK_GUARD_PATH)

    files = _discover_pending_preflop_files()
    results = [_run_one(display_module, bridge_module, guard_module, path) for path in files]

    ok_results = [item for item in results if item.get("ok") is True]
    bad_results = [item for item in results if item.get("ok") is not True]

    action_counts: dict[str, int] = {}
    for item in results:
        action = str(item.get("action") or "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1

    report = {
        "schema": "pokervision_solver_preflop_v24_snapshot_click_guard_eligibility_check_v1",
        "status": "ok" if all(static_checks.values()) and files and not bad_results else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_display": str(DISPLAY_FILE),
        "snapshot_bridge": str(BRIDGE_PATH),
        "click_guard": str(CLICK_GUARD_PATH),
        "pending_root": str(PENDING_ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "static_checks": static_checks,
        "files_total": len(files),
        "ok_count": len(ok_results),
        "bad_count": len(bad_results),
        "action_counts": action_counts,
        "results": results,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
