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
BRIDGE_PATH = SNAPSHOT_ROOT / "runtime" / "solver_preflop_dryrun_bridge.py"
TABLE_SLOTS_PATH = SNAPSHOT_ROOT / "table_slots.py"
PENDING_ROOT = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle" / "Clear_JSON_Pending"
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v28_snapshot_6slot_isolation_audit"


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean_output_dir() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _discover_preflop_pending_files() -> list[Path]:
    if not PENDING_ROOT.exists():
        return []
    return sorted(PENDING_ROOT.glob("table_*/*preflop*.json"))


def _table_id_from_path(path: Path) -> str:
    parent = path.parent.name
    return parent if parent.startswith("table_") else "unknown_table"


def _replace_strings(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        text = value
        for old, new in replacements.items():
            if old:
                text = text.replace(old, new)
        return text
    if isinstance(value, list):
        return [_replace_strings(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_strings(item, replacements) for key, item in value.items()}
    return value


def _center_from_bbox(slot_bbox: dict[str, Any]) -> tuple[float, float]:
    x1 = float(slot_bbox["x1"])
    y1 = float(slot_bbox["y1"])
    x2 = float(slot_bbox["x2"])
    y2 = float(slot_bbox["y2"])
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


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
    slot_payload: dict[str, Any],
    target_button: str,
    decision_id: str,
    action: str,
) -> dict[str, Any]:
    table = dict(pending_clear.get("table")) if isinstance(pending_clear.get("table"), dict) else {}
    table.update(slot_payload)
    slot_bbox = table["slot_bbox"]
    cx, cy = _center_from_bbox(slot_bbox)

    return {
        "schema": "v28_snapshot_6slot_isolation_audit_dark_state",
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
                            "x": cx,
                            "y": cy,
                        },
                    }
                ],
            }
        },
    }


def _prepare_synthetic_case(
    *,
    template_path: Path,
    table_id: str,
    slot_payload: dict[str, Any],
) -> dict[str, Any]:
    original_table_id = _table_id_from_path(template_path)
    original_payload = _load_json(template_path)
    original_frame_id = str(original_payload.get("frame_id") or template_path.stem.replace(".pending", ""))
    synthetic_frame_id = f"{table_id}_v28_isolation_preflop"

    replacements = {
        original_frame_id: synthetic_frame_id,
        original_table_id: table_id,
    }

    payload = _replace_strings(copy.deepcopy(original_payload), replacements)
    payload["frame_id"] = synthetic_frame_id

    # Clear_JSON schema forbids technical table/slot fields.
    # Slot isolation is audited through file paths, frame_id scoping,
    # runtime plan directories, synthetic Dark/runtime state and guard input.
    payload.pop("table", None)

    if "table_id" in payload:
        payload["table_id"] = table_id
    if "source_frame_id" in payload:
        payload["source_frame_id"] = synthetic_frame_id

    return payload


def _run_one(
    *,
    display_module: Any,
    bridge_module: Any,
    pending_clear: dict[str, Any],
    table_id: str,
    slot_payload: dict[str, Any],
    source_template: Path,
) -> dict[str, Any]:
    source_frame_id = str(pending_clear.get("frame_id") or f"{table_id}_v28_isolation_preflop")

    case_path = OUT_DIR / "_synthetic_pending_cases" / table_id / f"{source_frame_id}.pending.json"
    _write_json(case_path, pending_clear)

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
        slot_payload=slot_payload,
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

    final_clear = dict(pending_clear)
    final_clear["click_result"] = dict(compact_click_result)
    final_validation = display_module.validate_clear_json_contract(final_clear)

    final_clear_path = None
    saved_final = {}
    if (
        isinstance(pending_validation, dict)
        and pending_validation.get("ok")
        and isinstance(click_execution_guard_report, dict)
        and click_execution_guard_report.get("guard_passed") is True
        and not isinstance(final_publication_block, dict)
        and isinstance(final_validation, dict)
        and final_validation.get("ok")
    ):
        final_clear_path = display_module.save_clear_table_frame_json(
            clear_state=final_clear,
            cycle_dir=OUT_DIR,
            table_id=table_id,
        )
        saved_final = _load_json(Path(final_clear_path))

    saved_click = saved_final.get("click_result") if isinstance(saved_final.get("click_result"), dict) else {}
    synthetic_dark_table = synthetic_state.get("table") if isinstance(synthetic_state.get("table"), dict) else {}

    runtime_path = str(final_runtime_plan_contract.get("path") or "")
    final_path = str(final_clear_path or "")

    checks = {
        "table_id_matches_case": str(saved_final.get("frame_id") or "").startswith(table_id),
        "slot_bbox_matches_case": synthetic_dark_table.get("slot_bbox") == slot_payload.get("slot_bbox"),
        "solver_source_selected": selection.get("selected_source") == "Solver_Preflop_Bridge",
        "pending_runtime_preview_expected": pending_runtime_plan_contract.get("status") == "preview_not_saved_pending_only",
        "final_runtime_plan_saved": final_runtime_plan_contract.get("status") == "saved",
        "runtime_path_scoped_to_table": f"Action_Runtime_Plan_JSON\\{table_id}\\" in runtime_path,
        "click_execution_guard_passed": isinstance(click_execution_guard_report, dict) and click_execution_guard_report.get("guard_passed") is True,
        "compact_click_result_schema_safe": set(compact_click_result.keys()) == {
            "status",
            "decision_id",
            "dry_run",
            "real_click_enabled",
        },
        "final_validation_ok": isinstance(final_validation, dict) and final_validation.get("ok") is True,
        "final_clear_saved": bool(final_clear_path and Path(final_clear_path).exists()),
        "final_path_scoped_to_table": f"Clear_JSON\\{table_id}\\" in final_path,
        "saved_final_contains_same_click_result": saved_click == compact_click_result,
        "frame_id_scoped_to_table": str(saved_final.get("frame_id") or "").startswith(table_id),
    }

    return {
        "table_id": table_id,
        "table_index": slot_payload.get("table_index"),
        "source_template": str(source_template.relative_to(PROJECT_ROOT)),
        "synthetic_pending_case": str(case_path.relative_to(PROJECT_ROOT)),
        "source_frame_id": source_frame_id,
        "selected_source": selection.get("selected_source"),
        "selection_reason": selection.get("reason"),
        "decision_id": decision_id,
        "action": action,
        "target_button": target_button,
        "slot_bbox": slot_payload.get("slot_bbox"),
        "pending_validation": pending_validation,
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
        "click_execution_guard": {
            "status": click_execution_guard_report.get("status") if isinstance(click_execution_guard_report, dict) else None,
            "reason": click_execution_guard_report.get("reason") if isinstance(click_execution_guard_report, dict) else None,
            "guard_passed": click_execution_guard_report.get("guard_passed") if isinstance(click_execution_guard_report, dict) else None,
            "message": click_execution_guard_report.get("message") if isinstance(click_execution_guard_report, dict) else None,
        },
        "compact_click_result": compact_click_result,
        "final_publication_block": final_publication_block,
        "final_clear": {
            "validation": final_validation,
            "path": str(final_clear_path) if final_clear_path else None,
            "exists": bool(final_clear_path and Path(final_clear_path).exists()),
            "saved_frame_id": saved_final.get("frame_id") if isinstance(saved_final, dict) else None,
            "saved_table_id": None,
            "saved_slot_bbox": None,
            "synthetic_guard_slot_bbox": synthetic_dark_table.get("slot_bbox"),
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
    if not TABLE_SLOTS_PATH.exists():
        raise FileNotFoundError(TABLE_SLOTS_PATH)

    _clean_output_dir()

    os.environ["POKERVISION_SOLVER_PREFLOP_ROOT"] = str(PROJECT_ROOT)
    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))

    display_module = _load_module("v28_snapshot_display_analysis_cycle", DISPLAY_FILE)
    bridge_module = _load_module("v28_solver_preflop_bridge", BRIDGE_PATH)
    table_slots_module = _load_module("v28_table_slots", TABLE_SLOTS_PATH)

    slots = list(table_slots_module.list_table_slots())
    source_files = _discover_preflop_pending_files()
    if not source_files:
        raise RuntimeError("No preflop pending files found for synthetic 6-slot audit.")

    source_by_table: dict[str, Path] = {}
    for path in source_files:
        source_by_table.setdefault(_table_id_from_path(path), path)

    results = []
    for idx, slot in enumerate(slots):
        table_id = str(slot.table_id)
        template = source_by_table.get(table_id) or source_files[idx % len(source_files)]
        slot_payload = slot.to_json()
        pending_clear = _prepare_synthetic_case(
            template_path=template,
            table_id=table_id,
            slot_payload=slot_payload,
        )
        results.append(
            _run_one(
                display_module=display_module,
                bridge_module=bridge_module,
                pending_clear=pending_clear,
                table_id=table_id,
                slot_payload=slot_payload,
                source_template=template,
            )
        )

    expected_table_ids = [f"table_{index:02d}" for index in range(1, 7)]
    result_table_ids = [str(item.get("table_id")) for item in results]
    decision_ids = [str(item.get("decision_id") or "") for item in results]

    runtime_files = sorted(str(path) for path in OUT_DIR.rglob("Action_Runtime_Plan_JSON/**/*.json"))
    final_files = sorted(str(path) for path in OUT_DIR.rglob("Clear_JSON/**/*.json"))

    slot_checks = {
        "six_slots_defined": len(slots) == 6,
        "expected_table_ids_present": result_table_ids == expected_table_ids,
        "unique_table_ids": len(set(result_table_ids)) == 6,
        "unique_table_indexes": len({item.get("table_index") for item in results}) == 6,
        "unique_slot_bboxes": len({json.dumps(item.get("slot_bbox"), sort_keys=True) for item in results}) == 6,
        "unique_decision_ids": len(set(decision_ids)) == 6,
        "runtime_file_per_table": len(runtime_files) == 6,
        "final_clear_file_per_table": len(final_files) == 6,
        "all_runtime_dirs_scoped": all(f"Action_Runtime_Plan_JSON\\{table_id}\\" in "\n".join(runtime_files) for table_id in expected_table_ids),
        "all_final_dirs_scoped": all(f"Clear_JSON\\{table_id}\\" in "\n".join(final_files) for table_id in expected_table_ids),
    }

    ok_results = [item for item in results if item.get("ok") is True]
    bad_results = [item for item in results if item.get("ok") is not True]

    report = {
        "schema": "pokervision_solver_preflop_v28_snapshot_6slot_isolation_audit_v1",
        "status": "ok" if all(slot_checks.values()) and len(results) == 6 and not bad_results else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_display": str(DISPLAY_FILE),
        "snapshot_bridge": str(BRIDGE_PATH),
        "table_slots": str(TABLE_SLOTS_PATH),
        "pending_root": str(PENDING_ROOT),
        "out_dir": str(OUT_DIR),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "source_preflop_files_count": len(source_files),
        "synthetic_6slot_cases": True,
        "slot_checks": slot_checks,
        "files_total": len(results),
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
