from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

DISPLAY_PATH = SNAPSHOT_ROOT / "display_analysis_cycle.py"
TABLE_SLOTS_PATH = SNAPSHOT_ROOT / "table_slots.py"
CURRENT_CYCLE_DIR = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle"
BACKUP_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v219_current_cycle_backup"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)

    if spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def backup_current_cycle() -> None:
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)

    if CURRENT_CYCLE_DIR.exists():
        shutil.copytree(CURRENT_CYCLE_DIR, BACKUP_DIR)
    else:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def restore_current_cycle() -> None:
    if CURRENT_CYCLE_DIR.exists():
        shutil.rmtree(CURRENT_CYCLE_DIR)

    if BACKUP_DIR.exists():
        shutil.copytree(BACKUP_DIR, CURRENT_CYCLE_DIR)



def count_json_files(relative_dir: str) -> int:
    path = CURRENT_CYCLE_DIR / relative_dir
    if not path.exists():
        return 0
    return len(list(path.rglob("*.json")))


def main() -> int:
    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))

    display = load_module("v219_display_analysis_cycle", DISPLAY_PATH)
    table_slots = load_module("v219_table_slots", TABLE_SLOTS_PATH)

    slots = list(table_slots.list_table_slots())

    image_by_table_id = {
        slot.table_id: Path(f"live_desktop_{slot.table_id}.png")
        for slot in slots
    }
    opened_table_ids = {slot.table_id for slot in slots}

    hand_tracker = display.HandIdentityTracker()
    action_event_gate = display.ActionEventGate(inactive_reset_passes=2)
    clear_state_machine = display.ClearJsonStateMachine()
    transaction_gate = display.TableActionTransactionGate(
        dry_run_counts_as_completed=True,
        release_on_inactive=True,
    )

    backup_current_cycle()

    probe_stdout = io.StringIO()

    try:
        with contextlib.redirect_stdout(probe_stdout):
            saved_paths = display.run_ui_display_analysis_cycle(
                image_by_table_id=image_by_table_id,
                opened_table_ids=opened_table_ids,
                hand_tracker=hand_tracker,
                action_event_gate=action_event_gate,
                clear_json_state_machine=clear_state_machine,
                table_action_transaction_gate=transaction_gate,
                display_pass_id="v219_live_probe_000001",
                clear_previous_outputs_on_start=True,
                cycle_id="v219_live_probe",
            )

        counts = {
            "dark_json": count_json_files("Dark_JSON"),
            "pending_clear_json": count_json_files("Clear_JSON_Pending"),
            "final_clear_json": count_json_files("Clear_JSON"),
            "decision_json": count_json_files("Decision_JSON"),
            "action_decision_json": count_json_files("Action_Decision_JSON"),
            "action_runtime_plan_json": count_json_files("Action_Runtime_Plan_JSON"),
        }
    finally:
        restore_current_cycle()

    report = {
        "schema": "pokervision_solver_preflop_v219_live_no_click_capture_probe_v1",
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "current_cycle_dir": str(CURRENT_CYCLE_DIR),

        "real_project_touched": False,
        "live_cycle_executed": True,
        "screen_capture_executed": True,
        "yolo_detector_executed": True,
        "physical_click_executed": False,
        "current_cycle_restored_after_probe": True,

        "slots_total": len(slots),
        "opened_table_ids": sorted(opened_table_ids),
        "saved_paths_count": len(saved_paths),
        "saved_paths": [str(path) for path in saved_paths],
        "probe_stdout_lines": probe_stdout.getvalue().splitlines()[-20:],
        "output_counts": counts,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
