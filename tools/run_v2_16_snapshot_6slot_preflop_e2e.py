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
TABLE_SLOTS_PATH = SNAPSHOT_ROOT / "table_slots.py"
PENDING_ROOT = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle" / "Clear_JSON_Pending"

OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v216_snapshot_6slot_preflop_e2e"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)

    if spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def clean_output_dir() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def replace_strings(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        result = value
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result

    if isinstance(value, list):
        return [replace_strings(item, replacements) for item in value]

    if isinstance(value, dict):
        return {key: replace_strings(item, replacements) for key, item in value.items()}

    return value


def table_id_from_path(path: Path) -> str:
    parent = path.parent.name
    return parent if parent.startswith("table_") else "table_01"


def discover_preflop_files() -> list[Path]:
    return sorted(PENDING_ROOT.glob("table_*/*preflop*.json"))


def prepare_synthetic_clear_state(
    *,
    template_path: Path,
    table_id: str,
) -> dict[str, Any]:
    original_table_id = table_id_from_path(template_path)
    original_payload = load_json(template_path)
    original_frame_id = str(original_payload.get("frame_id") or template_path.stem.replace(".pending", ""))

    synthetic_frame_id = f"{table_id}_v216_preflop_e2e"

    payload = replace_strings(
        copy.deepcopy(original_payload),
        {
            original_table_id: table_id,
            original_frame_id: synthetic_frame_id,
        },
    )

    payload["frame_id"] = synthetic_frame_id

    payload.pop("click_result", None)
    payload.pop("table", None)
    payload.pop("hand_id", None)

    if "table_id" in payload:
        payload["table_id"] = table_id

    if "source_frame_id" in payload:
        payload["source_frame_id"] = synthetic_frame_id

    return payload


def center_from_bbox(slot_bbox: dict[str, Any]) -> tuple[float, float]:
    x1 = float(slot_bbox["x1"])
    y1 = float(slot_bbox["y1"])
    x2 = float(slot_bbox["x2"])
    y2 = float(slot_bbox["y2"])

    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def build_runtime_action(
    *,
    decision_id: str,
    slot_bbox: dict[str, Any],
) -> dict[str, Any]:
    cx, cy = center_from_bbox(slot_bbox)

    return {
        "service": {
            "status": "skipped",
            "reason": "service_skipped",
        },
        "action_button": {
            "status": "dry_run",
            "reason": "v216_snapshot_6slot_dry_run_completed",
            "decision_id": decision_id,
            "solver_action": "fold",
            "dry_run": True,
            "real_click_enabled": False,
            "guard_passed": True,
            "message": "V2.16 synthetic 6-slot dry-run completed.",
            "click_points": [
                {
                    "class_name": "FOLD",
                    "global_click_point": {
                        "x": cx,
                        "y": cy,
                    },
                    "inside_slot_bbox": True,
                }
            ],
        },
    }


def build_dark_state(
    *,
    table_id: str,
    frame_id: str,
    slot_payload: dict[str, Any],
    runtime_action: dict[str, Any],
    transaction_report: dict[str, Any],
) -> dict[str, Any]:
    table = dict(slot_payload)
    table["table_id"] = table_id
    table["slot_id"] = table_id

    return {
        "schema": "v216_snapshot_6slot_preflop_e2e_dark_state",
        "table": table,
        "frame_id": frame_id,
        "frame_name": frame_id,
        "runtime_action": runtime_action,
        "action_transaction_runtime": transaction_report,
        "errors": [],
        "warnings": [],
    }


def passing_click_guard_report(**kwargs):
    click_result = kwargs.get("click_result")

    if not isinstance(click_result, dict):
        click_result = {}

    return {
        "schema_version": "click_result_v09",
        "status": "dry_run",
        "reason": "v216_audit_click_guard_passed",
        "message": "V2.16 snapshot 6-slot E2E uses synthetic dry-run click guard only.",
        "guard_passed": True,
        "decision_id": click_result.get("decision_id"),
        "dry_run": True,
        "real_click_enabled": False,
        "guards": {
            "v216_snapshot_6slot_e2e_override": True,
        },
        "source": "V2.16Snapshot6SlotPreflopE2E",
    }


def main() -> int:
    clean_output_dir()

    os.environ["POKERVISION_SOLVER_PREFLOP_ROOT"] = str(PROJECT_ROOT)

    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))

    display = load_module("v216_display_analysis_cycle", DISPLAY_FILE)
    gate_module = load_module("v216_table_action_transaction_gate", GATE_PATH)
    table_slots_module = load_module("v216_table_slots", TABLE_SLOTS_PATH)

    gate_cls = gate_module.TableActionTransactionGate

    slots = list(table_slots_module.list_table_slots())
    source_files = discover_preflop_files()

    source_by_table: dict[str, Path] = {}
    for path in source_files:
        source_by_table.setdefault(table_id_from_path(path), path)

    original_builder = display.build_clear_json_from_dark_state
    original_click_guard = display._build_click_execution_guard_report

    results = []

    try:
        display._build_click_execution_guard_report = passing_click_guard_report

        for index, slot in enumerate(slots):
            table_id = str(slot.table_id)
            slot_payload = slot.to_json()
            template_path = source_by_table.get(table_id) or source_files[index % len(source_files)]

            clear_state = prepare_synthetic_clear_state(
                template_path=template_path,
                table_id=table_id,
            )

            frame_id = str(clear_state.get("frame_id"))
            decision_id = f"v216_{frame_id}"

            gate = gate_cls(
                dry_run_counts_as_completed=True,
                release_on_inactive=True,
            )

            gate.begin_analysis_cycle(
                table_id=table_id,
                action_event_id=f"evt_{frame_id}",
                action_signature=f"sig_{frame_id}",
            )

            gate.begin_action_cycle(
                table_id=table_id,
                action_event_id=f"evt_{frame_id}",
                action_signature=f"sig_{frame_id}",
            )

            runtime_action = build_runtime_action(
                decision_id=decision_id,
                slot_bbox=slot_payload["slot_bbox"],
            )

            transaction_report = gate.finalize_from_runtime(
                table_id=table_id,
                runtime_action=runtime_action,
            )

            clear_json_save_allowed = bool(transaction_report.get("click_completed"))

            click_result = transaction_report.get("click_result")
            if not isinstance(click_result, dict):
                click_result = None

            click_result_for_clear = click_result if clear_json_save_allowed else None

            display.build_clear_json_from_dark_state = (
                lambda state, payload=clear_state: copy.deepcopy(payload)
            )

            dark_path, final_path = display.save_dark_and_clear_table_frame_json(
                state=build_dark_state(
                    table_id=table_id,
                    frame_id=frame_id,
                    slot_payload=slot_payload,
                    runtime_action=runtime_action,
                    transaction_report=transaction_report,
                ),
                cycle_dir=OUT_DIR,
                table_id=table_id,
                hand_id=frame_id,
                frame_name=frame_id,
                active_confirmed=True,
                clear_json_state_machine=None,
                clear_json_save_allowed=clear_json_save_allowed,
                clear_json_build_allowed=True,
                clear_json_build_block_reason=None,
                click_result=click_result_for_clear,
            )

            dark_state = load_json(Path(dark_path))
            contract = dark_state.get("clear_json_contract", {})

            decision_contract = contract.get("decision_json_contract", {})
            action_contract = contract.get("action_decision_contract", {})
            runtime_contract = action_contract.get("action_runtime_plan_contract", {})
            solver_bridge = action_contract.get("solver_preflop_bridge_contract", {})
            source_selection = runtime_contract.get("v20_runtime_source_selection", {})

            final_exists = bool(final_path and Path(final_path).exists())
            final_state = load_json(Path(final_path)) if final_exists else {}

            runtime_path = str(runtime_contract.get("path") or "")
            final_path_text = str(final_path or "")

            checks = {
                "transaction_completed": transaction_report.get("click_completed") is True,
                "final_clear_saved": final_exists,
                "final_click_result_saved": isinstance(final_state.get("click_result"), dict),

                "frame_scoped_to_table": str(final_state.get("frame_id") or "").startswith(table_id),
                "runtime_path_scoped_to_table": f"Action_Runtime_Plan_JSON\\{table_id}\\" in runtime_path,
                "final_path_scoped_to_table": f"Clear_JSON\\{table_id}\\" in final_path_text,

                "contract_saved": contract.get("status") == "saved",
                "decision_json_saved": decision_contract.get("status") == "saved",
                "action_decision_saved": action_contract.get("status") == "saved",
                "runtime_plan_saved": runtime_contract.get("status") == "saved",
                "runtime_plan_final": runtime_contract.get("publication_stage") == "final",

                "solver_bridge_ok": solver_bridge.get("status") == "ok",
                "runtime_source_solver": source_selection.get("selected_source") == "Solver_Preflop_Bridge",
                "runtime_reason_solver": source_selection.get("reason") == "v20_solver_preflop_selected",
            }

            results.append(
                {
                    "table_id": table_id,
                    "table_index": slot_payload.get("table_index"),
                    "slot_bbox": slot_payload.get("slot_bbox"),
                    "source_template": str(template_path.relative_to(PROJECT_ROOT)),
                    "frame_id": frame_id,
                    "decision_id": decision_id,
                    "dark_path": str(dark_path),
                    "final_path": str(final_path) if final_path else None,
                    "transaction_status": transaction_report.get("status"),
                    "solver_bridge_status": solver_bridge.get("status"),
                    "runtime_selected_source": source_selection.get("selected_source"),
                    "runtime_selection_reason": source_selection.get("reason"),
                    "checks": checks,
                    "ok": all(checks.values()),
                }
            )

    finally:
        display.build_clear_json_from_dark_state = original_builder
        display._build_click_execution_guard_report = original_click_guard

    final_files = sorted(str(path) for path in OUT_DIR.rglob("Clear_JSON/**/*.json"))
    runtime_files = sorted(str(path) for path in OUT_DIR.rglob("Action_Runtime_Plan_JSON/**/*.json"))

    expected_table_ids = [f"table_{index:02d}" for index in range(1, 7)]
    result_table_ids = [item["table_id"] for item in results]
    decision_ids = [item["decision_id"] for item in results]

    slot_checks = {
        "six_slots_defined": len(slots) == 6,
        "expected_table_ids_present": result_table_ids == expected_table_ids,
        "unique_table_ids": len(set(result_table_ids)) == 6,
        "unique_table_indexes": len({item["table_index"] for item in results}) == 6,
        "unique_slot_bboxes": len({json.dumps(item["slot_bbox"], sort_keys=True) for item in results}) == 6,
        "unique_decision_ids": len(set(decision_ids)) == 6,
        "runtime_file_per_table": len(runtime_files) == 6,
        "final_clear_file_per_table": len(final_files) == 6,
        "all_runtime_dirs_scoped": all(f"Action_Runtime_Plan_JSON\\{table_id}\\" in "\n".join(runtime_files) for table_id in expected_table_ids),
        "all_final_dirs_scoped": all(f"Clear_JSON\\{table_id}\\" in "\n".join(final_files) for table_id in expected_table_ids),
    }

    report = {
        "schema": "pokervision_solver_preflop_v216_snapshot_6slot_preflop_e2e_v1",
        "status": "ok" if all(slot_checks.values()) and all(item["ok"] for item in results) else "error",
        "project_root": str(PROJECT_ROOT),
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
        "ok_count": len([item for item in results if item["ok"]]),
        "bad_count": len([item for item in results if not item["ok"]]),
        "published_runtime_files_count": len(runtime_files),
        "published_final_clear_files_count": len(final_files),
        "results": results,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
