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
PENDING_ROOT = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle" / "Clear_JSON_Pending"
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v22_solver_source_multicase_check"


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


def _run_one(display_module: Any, bridge_module: Any, path: Path) -> dict[str, Any]:
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
    decision_context = selected_state.get("decision_context") if isinstance(selected_state, dict) else {}

    selected_ok = (
        selection.get("selected_source") == "Solver_Preflop_Bridge"
        and selection.get("reason") == "v20_solver_preflop_selected"
        and selection.get("adapted_to_legacy_action_decision") is True
    )

    adapted_ok = (
        selected_state.get("source") == "Decision_JSON"
        and selected_state.get("status") == "ok"
        and selected_state.get("dry_run_safe") is True
        and selected_state.get("solver_stub") is True
        and isinstance(decision_context, dict)
        and decision_context.get("solver_preflop_runtime_source") is True
        and decision_context.get("solver_stub_legacy_compat") is True
    )

    runtime_ok = (
        runtime_plan_contract.get("status") == "preview_not_saved_pending_only"
        and runtime_plan_contract.get("file_publication_enabled") is False
        and isinstance(runtime_state, dict)
        and runtime_state.get("status") == "ok"
        and runtime_state.get("runtime_branch") == "action_button"
        and runtime_state.get("dry_run") is True
        and runtime_state.get("real_click_enabled") is False
        and isinstance(runtime_state.get("target_sequence"), list)
        and len(runtime_state.get("target_sequence")) > 0
    )

    expected_sequence = bridge_contract.get("click_sequence")
    plan_sequence = runtime_plan_contract.get("target_sequence")
    sequence_ok = False
    if selected_state.get("action") == "fold":
        sequence_ok = plan_sequence == ["FOLD"]
    elif selected_state.get("action") == "check":
        sequence_ok = plan_sequence == ["Check"]
    elif selected_state.get("action") == "call":
        sequence_ok = plan_sequence in (["Call"], ["CALL"])
    else:
        sequence_ok = isinstance(plan_sequence, list) and len(plan_sequence) > 0

    return {
        "file": str(path.relative_to(PROJECT_ROOT)),
        "table_id": table_id,
        "source_frame_id": bridge_contract.get("source_frame_id"),
        "bridge_status": bridge_contract.get("status"),
        "bridge_raw_action": bridge_contract.get("raw_action"),
        "bridge_engine_action": bridge_contract.get("engine_action"),
        "bridge_click_sequence": expected_sequence,
        "selection": selection,
        "selected_action_decision": {
            "source": selected_state.get("source"),
            "source_decision_frame_id": selected_state.get("source_decision_frame_id"),
            "action": selected_state.get("action"),
            "target_button_classes": selected_state.get("target_button_classes"),
            "solver_stub": selected_state.get("solver_stub"),
            "decision_context": decision_context,
        },
        "runtime_plan_contract": {
            "status": runtime_plan_contract.get("status"),
            "planned_action": runtime_plan_contract.get("planned_action"),
            "target_sequence": runtime_plan_contract.get("target_sequence"),
            "target_sequences": runtime_plan_contract.get("target_sequences"),
            "file_publication_enabled": runtime_plan_contract.get("file_publication_enabled"),
            "runtime_state_status": runtime_state.get("status") if isinstance(runtime_state, dict) else None,
            "dry_run": runtime_state.get("dry_run") if isinstance(runtime_state, dict) else None,
            "real_click_enabled": runtime_state.get("real_click_enabled") if isinstance(runtime_state, dict) else None,
        },
        "checks": {
            "selected_ok": selected_ok,
            "adapted_ok": adapted_ok,
            "runtime_ok": runtime_ok,
            "sequence_ok": sequence_ok,
        },
        "ok": bool(selected_ok and adapted_ok and runtime_ok and sequence_ok),
    }


def main() -> int:
    if not DISPLAY_FILE.exists():
        raise FileNotFoundError(DISPLAY_FILE)
    if not BRIDGE_PATH.exists():
        raise FileNotFoundError(BRIDGE_PATH)

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

    display_module = _load_module("v22_snapshot_display_analysis_cycle", DISPLAY_FILE)
    bridge_module = _load_module("v22_solver_preflop_bridge", BRIDGE_PATH)

    files = _discover_pending_preflop_files()
    results = [_run_one(display_module, bridge_module, path) for path in files]

    ok_results = [item for item in results if item.get("ok") is True]
    bad_results = [item for item in results if item.get("ok") is not True]
    action_counts: dict[str, int] = {}
    for item in results:
        action = str((item.get("selected_action_decision") or {}).get("action") or "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1

    report = {
        "schema": "pokervision_solver_preflop_v22_snapshot_solver_source_multicase_check_v1",
        "status": "ok" if all(static_checks.values()) and files and not bad_results else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_display": str(DISPLAY_FILE),
        "snapshot_bridge": str(BRIDGE_PATH),
        "pending_root": str(PENDING_ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
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
