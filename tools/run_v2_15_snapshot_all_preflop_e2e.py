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

OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v215_snapshot_all_preflop_e2e"


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


def make_safe_clear_state(payload: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(payload)

    result.pop("click_result", None)
    result.pop("table", None)
    result.pop("hand_id", None)

    return result


def build_runtime_action(decision_id: str) -> dict[str, Any]:
    return {
        "service": {
            "status": "skipped",
            "reason": "service_skipped",
        },
        "action_button": {
            "status": "dry_run",
            "reason": "v215_snapshot_dry_run_completed",
            "decision_id": decision_id,
            "solver_action": "fold",
            "dry_run": True,
            "real_click_enabled": False,
            "guard_passed": True,
            "message": "V2.15 snapshot dry-run completed.",
        },
    }


def build_dark_state(
    *,
    table_id: str,
    frame_id: str,
    runtime_action: dict[str, Any],
    transaction_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "v215_snapshot_all_preflop_e2e_dark_state",
        "table": {
            "table_id": table_id,
            "slot_id": table_id,
            "slot_bbox": {
                "x1": 0.0,
                "y1": 0.0,
                "x2": 100.0,
                "y2": 100.0,
            },
            "action_event_id": f"evt_{frame_id}",
        },
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
        "reason": "v215_audit_click_guard_passed",
        "message": "V2.15 snapshot E2E isolates final publication and Solver_Preflop runtime source.",
        "guard_passed": True,
        "decision_id": click_result.get("decision_id"),
        "dry_run": True,
        "real_click_enabled": False,
        "guards": {
            "v215_snapshot_e2e_override": True,
        },
        "source": "V2.15SnapshotAllPreflopE2E",
    }


def main() -> int:
    clean_output_dir()

    os.environ["POKERVISION_SOLVER_PREFLOP_ROOT"] = str(PROJECT_ROOT)

    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))

    display = load_module("v215_display_analysis_cycle", DISPLAY_FILE)
    gate_module = load_module("v215_table_action_transaction_gate", GATE_PATH)
    gate_cls = gate_module.TableActionTransactionGate

    source_files = sorted(PENDING_ROOT.glob("table_*/*preflop*.json"))

    original_builder = display.build_clear_json_from_dark_state
    original_click_guard = display._build_click_execution_guard_report

    results = []

    try:
        display._build_click_execution_guard_report = passing_click_guard_report

        for source_path in source_files:
            table_id = source_path.parent.name

            source_clear_state = make_safe_clear_state(load_json(source_path))
            frame_id = str(source_clear_state.get("frame_id") or source_path.stem.replace(".pending", ""))
            decision_id = f"v215_{frame_id}"

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

            runtime_action = build_runtime_action(decision_id)

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
                lambda state, payload=source_clear_state: copy.deepcopy(payload)
            )

            dark_path, final_path = display.save_dark_and_clear_table_frame_json(
                state=build_dark_state(
                    table_id=table_id,
                    frame_id=frame_id,
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

            checks = {
                "transaction_completed": transaction_report.get("click_completed") is True,
                "final_clear_saved": final_exists,
                "final_click_result_saved": isinstance(final_state.get("click_result"), dict),

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
                    "source": str(source_path),
                    "table_id": table_id,
                    "frame_id": frame_id,
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

    final_files = sorted(OUT_DIR.rglob("Clear_JSON/**/*.json"))
    runtime_files = sorted(OUT_DIR.rglob("Action_Runtime_Plan_JSON/**/*.json"))

    checks = {
        "source_preflop_files_count": len(source_files) == 4,
        "all_cases_ok": all(item["ok"] for item in results),
        "final_files_count": len(final_files) == len(source_files),
        "runtime_files_count": len(runtime_files) == len(source_files),
    }

    report = {
        "schema": "pokervision_solver_preflop_v215_snapshot_all_preflop_e2e_v1",
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "out_dir": str(OUT_DIR),

        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,

        "checks": checks,
        "files_total": len(source_files),
        "ok_count": len([item for item in results if item["ok"]]),
        "bad_count": len([item for item in results if not item["ok"]]),
        "final_files_count": len(final_files),
        "runtime_files_count": len(runtime_files),
        "results": results,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
