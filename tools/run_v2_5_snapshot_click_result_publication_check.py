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
CLICK_GUARD_PATH = SNAPSHOT_ROOT / "logic" / "click_execution_guard.py"
PENDING_ROOT = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle" / "Clear_JSON_Pending"
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v25_snapshot_click_result_publication"


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


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


def _clean_output_dir() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _click_result_path(table_id: str, source_frame_id: str) -> Path:
    safe_frame = str(source_frame_id or "unknown_frame").replace("\\", "_").replace("/", "_")
    return OUT_DIR / "Click_Result_JSON" / table_id / f"{safe_frame}.click_result.json"


def _runtime_plan_path(table_id: str, source_frame_id: str) -> Path:
    safe_frame = str(source_frame_id or "unknown_frame").replace("\\", "_").replace("/", "_")
    return OUT_DIR / "Action_Runtime_Plan_JSON" / table_id / f"{safe_frame}.runtime_plan.json"


def _build_click_request(
    *,
    guard_module: Any,
    table_id: str,
    source_frame_id: str,
    decision_id: str,
    action: str,
    target_button: str,
    runtime_state: dict[str, Any],
    dry_run: bool,
    real_click_enabled: bool,
    already_executed: tuple[str, ...] = tuple(),
):
    return guard_module.ClickExecutionRequest(
        table_id=table_id,
        hand_id=source_frame_id,
        street="preflop",
        decision_id=decision_id,
        action=action,
        target_button_class=target_button,
        click_point=(50.0, 50.0),
        slot_bbox=(0.0, 0.0, 100.0, 100.0),
        action_runtime_plan=runtime_state,
        already_executed_decision_ids=already_executed,
        dry_run=dry_run,
        real_click_enabled=real_click_enabled,
    )


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
        publish_files=True,
    )
    runtime_state = runtime_plan_contract.get("runtime_plan_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    source_frame_id = str(bridge_contract.get("source_frame_id") or runtime_state.get("source_action_decision_frame_id") or "")
    target_button = _target_button_from_plan(runtime_state)
    action = str(runtime_state.get("planned_action") or selected_state.get("action") or "")
    decision_id = str(selection.get("decision_id") or bridge_contract.get("decision_id") or source_frame_id)

    dry_request = _build_click_request(
        guard_module=guard_module,
        table_id=table_id,
        source_frame_id=source_frame_id,
        decision_id=decision_id,
        action=action,
        target_button=target_button,
        runtime_state=runtime_state,
        dry_run=True,
        real_click_enabled=False,
    )
    dry_result = guard_module.validate_click_execution_request(
        dry_request,
        guard_module.ClickGuardConfig(),
    )

    click_path = _click_result_path(table_id, source_frame_id)
    _write_json(click_path, dry_result)
    published_click_result = _load_json(click_path)

    runtime_path_text = runtime_plan_contract.get("path")
    runtime_path = Path(runtime_path_text) if runtime_path_text else _runtime_plan_path(table_id, source_frame_id)
    published_runtime_exists = bool(runtime_path and runtime_path.exists())

    forced_real_request = _build_click_request(
        guard_module=guard_module,
        table_id=table_id,
        source_frame_id=source_frame_id,
        decision_id=decision_id,
        action=action,
        target_button=target_button,
        runtime_state=runtime_state,
        dry_run=False,
        real_click_enabled=True,
    )
    forced_real_result = guard_module.validate_click_execution_request(
        forced_real_request,
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
        and dry_result.get("reason") == "all_click_execution_guards_passed"
        and dry_result.get("guard_passed") is True
        and dry_result.get("dry_run") is True
        and dry_result.get("real_click_enabled") is False
        and isinstance(dry_guards, dict)
        and dry_guards.get("plan_source_guard") is True
        and dry_guards.get("button_availability_guard") is True
        and dry_guards.get("slot_boundary_guard") is True
        and dry_guards.get("no_repeat_decision_guard") is True
        and dry_guards.get("dry_run_guard") is True
    )

    real_block_ok = (
        forced_real_result.get("status") == "blocked"
        and forced_real_result.get("reason") == "real_click_master_not_armed"
        and forced_real_result.get("guard_passed") is False
        and forced_real_result.get("dry_run") is False
        and forced_real_result.get("real_click_enabled") is True
    )

    click_published_ok = (
        click_path.exists()
        and isinstance(published_click_result, dict)
        and published_click_result.get("schema_version") == "click_result_v09"
        and published_click_result.get("status") == dry_result.get("status")
        and published_click_result.get("reason") == dry_result.get("reason")
        and published_click_result.get("decision_id") == decision_id
        and published_click_result.get("action") == action
        and published_click_result.get("target_button_class") == target_button
        and published_click_result.get("dry_run") is True
        and published_click_result.get("real_click_enabled") is False
        and published_click_result.get("guard_passed") is True
    )

    runtime_ok = (
        runtime_plan_contract.get("status") == "saved"
        and runtime_plan_contract.get("file_publication_enabled") is True
        and published_runtime_exists
        and runtime_state.get("status") == "ok"
        and runtime_state.get("dry_run") is True
        and runtime_state.get("real_click_enabled") is False
        and bool(target_button)
    )

    return {
        "file": str(path.relative_to(PROJECT_ROOT)),
        "table_id": table_id,
        "source_frame_id": source_frame_id,
        "selected_source": selection.get("selected_source"),
        "selection_reason": selection.get("reason"),
        "decision_id": decision_id,
        "action": action,
        "target_button": target_button,
        "runtime_plan": {
            "status": runtime_plan_contract.get("status"),
            "path": str(runtime_path),
            "exists": published_runtime_exists,
            "planned_action": runtime_state.get("planned_action"),
            "target_sequence": runtime_state.get("target_sequence"),
            "dry_run": runtime_state.get("dry_run"),
            "real_click_enabled": runtime_state.get("real_click_enabled"),
        },
        "click_result": {
            "status": dry_result.get("status"),
            "reason": dry_result.get("reason"),
            "path": str(click_path),
            "exists": click_path.exists(),
            "guard_passed": dry_result.get("guard_passed"),
            "dry_run": dry_result.get("dry_run"),
            "real_click_enabled": dry_result.get("real_click_enabled"),
            "published_status": published_click_result.get("status"),
            "published_reason": published_click_result.get("reason"),
            "published_guard_passed": published_click_result.get("guard_passed"),
        },
        "forced_real_click_result": {
            "status": forced_real_result.get("status"),
            "reason": forced_real_result.get("reason"),
            "guard_passed": forced_real_result.get("guard_passed"),
            "dry_run": forced_real_result.get("dry_run"),
            "real_click_enabled": forced_real_result.get("real_click_enabled"),
        },
        "checks": {
            "runtime_ok": bool(runtime_ok),
            "dry_run_guard_ok": bool(dry_ok),
            "click_published_ok": bool(click_published_ok),
            "real_click_block_ok": bool(real_block_ok),
        },
        "ok": bool(runtime_ok and dry_ok and click_published_ok and real_block_ok),
    }


def main() -> int:
    if not DISPLAY_FILE.exists():
        raise FileNotFoundError(DISPLAY_FILE)
    if not BRIDGE_PATH.exists():
        raise FileNotFoundError(BRIDGE_PATH)
    if not CLICK_GUARD_PATH.exists():
        raise FileNotFoundError(CLICK_GUARD_PATH)

    _clean_output_dir()

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

    display_module = _load_module("v25_snapshot_display_analysis_cycle", DISPLAY_FILE)
    bridge_module = _load_module("v25_solver_preflop_bridge", BRIDGE_PATH)
    guard_module = _load_module("v25_click_execution_guard", CLICK_GUARD_PATH)

    files = _discover_pending_preflop_files()
    results = [_run_one(display_module, bridge_module, guard_module, path) for path in files]

    ok_results = [item for item in results if item.get("ok") is True]
    bad_results = [item for item in results if item.get("ok") is not True]

    action_counts: dict[str, int] = {}
    for item in results:
        action = str(item.get("action") or "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1

    published_runtime_files = sorted(str(path) for path in OUT_DIR.rglob("Action_Runtime_Plan_JSON/**/*.json"))
    published_click_files = sorted(str(path) for path in OUT_DIR.rglob("Click_Result_JSON/**/*.json"))

    report = {
        "schema": "pokervision_solver_preflop_v25_snapshot_click_result_publication_check_v1",
        "status": "ok" if all(static_checks.values()) and files and not bad_results else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_display": str(DISPLAY_FILE),
        "snapshot_bridge": str(BRIDGE_PATH),
        "click_guard": str(CLICK_GUARD_PATH),
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
        "action_counts": action_counts,
        "published_runtime_files_count": len(published_runtime_files),
        "published_click_files_count": len(published_click_files),
        "published_runtime_files": published_runtime_files,
        "published_click_files": published_click_files,
        "results": results,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
