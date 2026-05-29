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
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v26_snapshot_final_clear_embedding"


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


def _clean_output_dir() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _build_compact_click_result(click_result: dict[str, Any]) -> dict[str, Any]:
    # Clear_JSON schema-safe compact click_result only.
    # Do NOT include click_completed here: snapshot clear_json_builder forbids it.
    return {
        "status": str(click_result.get("status") or ""),
        "decision_id": str(click_result.get("decision_id") or ""),
        "dry_run": bool(click_result.get("dry_run")),
        "real_click_enabled": bool(click_result.get("real_click_enabled")),
    }


def _build_click_request(
    *,
    guard_module: Any,
    table_id: str,
    source_frame_id: str,
    decision_id: str,
    action: str,
    target_button: str,
    runtime_state: dict[str, Any],
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
        already_executed_decision_ids=tuple(),
        dry_run=True,
        real_click_enabled=False,
    )


def _run_one(display_module: Any, bridge_module: Any, guard_module: Any, path: Path) -> dict[str, Any]:
    pending_clear = _load_json(path)
    table_id = _table_id_from_path(path)

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

    source_frame_id = str(bridge_contract.get("source_frame_id") or pending_clear.get("frame_id") or "")
    target_button = _target_button_from_plan(runtime_state)
    action = str(runtime_state.get("planned_action") or selected_state.get("action") or "")
    decision_id = str(selection.get("decision_id") or bridge_contract.get("decision_id") or source_frame_id)

    click_request = _build_click_request(
        guard_module=guard_module,
        table_id=table_id,
        source_frame_id=source_frame_id,
        decision_id=decision_id,
        action=action,
        target_button=target_button,
        runtime_state=runtime_state,
    )
    click_result = guard_module.validate_click_execution_request(
        click_request,
        guard_module.ClickGuardConfig(),
    )
    compact_click_result = _build_compact_click_result(click_result)

    final_clear = dict(pending_clear)
    final_clear["click_result"] = dict(compact_click_result)

    final_validation = display_module.validate_clear_json_contract(final_clear)
    final_path = None
    saved_final = {}
    if isinstance(final_validation, dict) and final_validation.get("ok"):
        final_path = display_module.save_clear_table_frame_json(
            clear_state=final_clear,
            cycle_dir=OUT_DIR,
            table_id=table_id,
        )
        saved_final = _load_json(Path(final_path))

    saved_click = saved_final.get("click_result") if isinstance(saved_final, dict) else {}

    compact_ok = (
        compact_click_result.get("status") == "dry_run"
        and bool(compact_click_result.get("decision_id"))
        and compact_click_result.get("dry_run") is True
        and compact_click_result.get("real_click_enabled") is False
        and set(compact_click_result.keys()) == {
            "status",
            "decision_id",
            "dry_run",
            "real_click_enabled",
        }
    )

    validation_ok = isinstance(final_validation, dict) and final_validation.get("ok") is True

    saved_ok = (
        final_path is not None
        and Path(final_path).exists()
        and isinstance(saved_final, dict)
        and saved_final.get("frame_id") == pending_clear.get("frame_id")
        and isinstance(saved_click, dict)
        and saved_click == compact_click_result
    )

    runtime_ok = (
        runtime_plan_contract.get("status") == "saved"
        and runtime_state.get("status") == "ok"
        and runtime_state.get("dry_run") is True
        and runtime_state.get("real_click_enabled") is False
        and bool(target_button)
    )

    click_ok = (
        click_result.get("status") == "dry_run"
        and click_result.get("reason") == "all_click_execution_guards_passed"
        and click_result.get("guard_passed") is True
        and click_result.get("dry_run") is True
        and click_result.get("real_click_enabled") is False
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
            "path": runtime_plan_contract.get("path"),
            "planned_action": runtime_state.get("planned_action"),
            "target_sequence": runtime_state.get("target_sequence"),
            "dry_run": runtime_state.get("dry_run"),
            "real_click_enabled": runtime_state.get("real_click_enabled"),
        },
        "click_result": {
            "status": click_result.get("status"),
            "reason": click_result.get("reason"),
            "guard_passed": click_result.get("guard_passed"),
            "click_completed_inferred": bool(click_result.get("guard_passed")),
            "dry_run": click_result.get("dry_run"),
            "real_click_enabled": click_result.get("real_click_enabled"),
        },
        "compact_click_result": compact_click_result,
        "final_clear": {
            "validation": final_validation,
            "path": str(final_path) if final_path else None,
            "exists": bool(final_path and Path(final_path).exists()),
            "frame_id": saved_final.get("frame_id") if isinstance(saved_final, dict) else None,
            "click_result": saved_click if isinstance(saved_click, dict) else None,
        },
        "checks": {
            "runtime_ok": bool(runtime_ok),
            "click_ok": bool(click_ok),
            "compact_click_result_ok": bool(compact_ok),
            "final_validation_ok": bool(validation_ok),
            "final_saved_ok": bool(saved_ok),
        },
        "ok": bool(runtime_ok and click_ok and compact_ok and validation_ok and saved_ok),
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

    display_module = _load_module("v26_snapshot_display_analysis_cycle", DISPLAY_FILE)
    bridge_module = _load_module("v26_solver_preflop_bridge", BRIDGE_PATH)
    guard_module = _load_module("v26_click_execution_guard", CLICK_GUARD_PATH)

    files = _discover_pending_preflop_files()
    results = [_run_one(display_module, bridge_module, guard_module, path) for path in files]

    ok_results = [item for item in results if item.get("ok") is True]
    bad_results = [item for item in results if item.get("ok") is not True]

    action_counts: dict[str, int] = {}
    for item in results:
        action = str(item.get("action") or "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1

    runtime_files = sorted(str(path) for path in OUT_DIR.rglob("Action_Runtime_Plan_JSON/**/*.json"))
    final_files = sorted(
        str(Path(item["final_clear"]["path"]))
        for item in results
        if isinstance(item.get("final_clear"), dict)
        and item["final_clear"].get("path")
        and item["final_clear"].get("exists") is True
    )

    report = {
        "schema": "pokervision_solver_preflop_v26_snapshot_final_clear_embedding_check_v1",
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
