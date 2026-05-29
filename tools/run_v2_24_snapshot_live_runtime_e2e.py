from __future__ import annotations

import copy
import importlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v224_snapshot_live_runtime_e2e"

SCHEMA = "pokervision_solver_preflop_v224_snapshot_live_runtime_e2e_v1"


@dataclass
class FakeActionButtonPipelineResult:
    status: str = "ok"
    detected_classes: List[str] = field(default_factory=list)
    best_by_class: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    raw_detection_count: int = 0
    processing_time_ms: int = 1
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def clean_output_dir() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def import_snapshot_modules() -> tuple[Any, Any, Any, Any]:
    os.environ["POKERVISION_SOLVER_PREFLOP_ROOT"] = str(PROJECT_ROOT)
    snapshot_text = str(SNAPSHOT_ROOT)
    project_text = str(PROJECT_ROOT)
    if snapshot_text not in sys.path:
        sys.path.insert(0, snapshot_text)
    if project_text not in sys.path:
        sys.path.insert(0, project_text)

    table_slots = importlib.import_module("table_slots")
    bridge = importlib.import_module("runtime.solver_preflop_dryrun_bridge")
    v11_runtime = importlib.import_module("runtime.v11_stage1_runtime")
    click_stub = importlib.import_module("runtime.action_click_stub")
    return table_slots, bridge, v11_runtime, click_stub


def make_unopened_btn_aa_clear_state() -> Dict[str, Any]:
    return {
        "frame_id": "table_01_v224_preflop_openraise_e2e",
        "board": {"cards": [], "street": "preflop"},
        "Total_pot": 1.5,
        "players": {
            "UTG": {"stack": 100.0, "fold": True, "chips": False},
            "MP": {"stack": 100.0, "fold": True, "chips": False},
            "CO": {"stack": 100.0, "fold": True, "chips": False},
            "BTN": {
                "hero": True,
                "cards": ["A_spades", "A_hearts"],
                "stack": 100.0,
                "fold": False,
                "chips": False,
            },
            "SB": {"stack": 100.0, "fold": False, "chips": 0.5},
            "BB": {"stack": 100.0, "fold": False, "chips": 1.0},
        },
    }


def seat_from_player(position: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    chips = payload.get("chips")
    stack = payload.get("stack")
    result = {
        "position": position,
        "fold": bool(payload.get("fold", False)),
        "stack": {
            "detect": stack is not None and stack is not False,
            "value": None if stack is False else stack,
        },
        "chips": {
            "detect": chips is not None and chips is not False,
            "value": None if chips is False else chips,
        },
    }
    if payload.get("hero") is True:
        result["hero_cards"] = list(payload.get("cards") or [])
    return result


def build_full_state_from_clear_state(
    *,
    clear_state: Dict[str, Any],
    table_id: str,
    slot_payload: Dict[str, Any],
    bridge_contract: Dict[str, Any],
) -> Dict[str, Any]:
    frame_id = str(clear_state.get("frame_id") or "v224_unknown_frame")
    players = clear_state.get("players") or {}
    hero_position = None
    for position, player in players.items():
        if isinstance(player, dict) and player.get("hero") is True:
            hero_position = str(position)
            break
    if not hero_position:
        raise ValueError("Synthetic Clear_JSON must contain exactly one hero player.")

    seat_positions = [hero_position] + [str(position) for position in players.keys() if str(position) != hero_position]
    seats: Dict[str, Any] = {}
    for index, position in enumerate(seat_positions, start=1):
        seats[f"Player_seat{index}"] = seat_from_player(position, players[position])

    return {
        "schema": "v224_snapshot_live_runtime_e2e_full_state",
        "table": {
            "table_id": table_id,
            "slot_id": table_id,
            "slot_bbox": slot_payload.get("slot_bbox"),
            "frame_id": frame_id,
            "frame_name": frame_id,
            "hand_id": "v224_hand_001",
            "action_event_id": f"evt_{frame_id}",
        },
        "frame_id": frame_id,
        "frame_name": frame_id,
        "runtime_event": {
            "should_process": True,
            "action_event_id": f"evt_{frame_id}",
            "action_signature": f"sig_{frame_id}",
        },
        "pipeline_meta": {
            "status": "ok",
            "processing_time_ms": 1,
        },
        "table_structure": {
            "classes": {
                "Board": {
                    "cards": list((clear_state.get("board") or {}).get("cards") or []),
                    "street": "preflop",
                },
                "Total_pot": {
                    "detect": True,
                    "value": clear_state.get("Total_pot"),
                },
            }
        },
        "players": {"seats": seats},
        "solver_preflop_bridge_contract": bridge_contract,
    }


def fake_action_button_result() -> FakeActionButtonPipelineResult:
    best_by_class = {
        "FOLD": {"class_name": "FOLD", "confidence": 0.99, "bbox_xyxy": [95, 505, 185, 555]},
        "33%": {"class_name": "33%", "confidence": 0.99, "bbox_xyxy": [260, 455, 330, 500]},
        "50%": {"class_name": "50%", "confidence": 0.99, "bbox_xyxy": [340, 455, 410, 500]},
        "70%": {"class_name": "70%", "confidence": 0.99, "bbox_xyxy": [420, 455, 490, 500]},
        "98%": {"class_name": "98%", "confidence": 0.99, "bbox_xyxy": [500, 455, 570, 500]},
        "Call": {"class_name": "Call", "confidence": 0.99, "bbox_xyxy": [210, 505, 300, 555]},
        "Check/fold": {"class_name": "Check/fold", "confidence": 0.99, "bbox_xyxy": [315, 505, 440, 555]},
        "Check": {"class_name": "Check", "confidence": 0.99, "bbox_xyxy": [455, 505, 545, 555]},
        "Bet/Raise": {"class_name": "Bet/Raise", "confidence": 0.99, "bbox_xyxy": [580, 505, 710, 555]},
    }
    return FakeActionButtonPipelineResult(
        status="ok",
        detected_classes=list(best_by_class.keys()),
        best_by_class=best_by_class,
        raw_detection_count=len(best_by_class),
        processing_time_ms=1,
    )


def force_dry_run_runtime(v11_runtime: Any, click_stub: Any) -> None:
    # Patch module-level imported config constants. This V2.24 tool must never
    # move the mouse, even when local config.py is in a real-click profile.
    for module in (v11_runtime, click_stub):
        if hasattr(module, "V11_REAL_MOUSE_CLICK_ENABLED"):
            setattr(module, "V11_REAL_MOUSE_CLICK_ENABLED", False)
        if hasattr(module, "V11_CLICK_DRY_RUN"):
            setattr(module, "V11_CLICK_DRY_RUN", True)
        if hasattr(module, "V09_REAL_CLICK_MASTER_ARMED"):
            setattr(module, "V09_REAL_CLICK_MASTER_ARMED", False)


def main() -> int:
    clean_output_dir()
    table_slots, bridge_module, v11_runtime, click_stub = import_snapshot_modules()
    force_dry_run_runtime(v11_runtime, click_stub)

    slot = table_slots.get_table_slot("table_01")
    slot_payload = slot.to_json()
    table_id = str(slot.table_id)
    clear_state = make_unopened_btn_aa_clear_state()

    bridge_contract = bridge_module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=copy.deepcopy(clear_state),
        cycle_dir=OUT_DIR,
        table_id=table_id,
        publish_files=False,
    )

    original_action_button_pipeline = v11_runtime.run_action_button_pipeline
    try:
        v11_runtime.run_action_button_pipeline = lambda **kwargs: fake_action_button_result()
        full_state = build_full_state_from_clear_state(
            clear_state=clear_state,
            table_id=table_id,
            slot_payload=slot_payload,
            bridge_contract=bridge_contract,
        )
        runtime_result = v11_runtime.run_v11_stage1_runtime(
            full_state=full_state,
            table_roi_image=None,
            slot=slot,
            active_confirmed=True,
            cycle_dir=OUT_DIR,
        )
    finally:
        v11_runtime.run_action_button_pipeline = original_action_button_pipeline

    solver = runtime_result.get("solver") if isinstance(runtime_result, dict) else {}
    click = runtime_result.get("click") if isinstance(runtime_result, dict) else {}
    action_buttons = runtime_result.get("action_buttons") if isinstance(runtime_result, dict) else {}
    bridge_payload = bridge_contract.get("bridge_payload") if isinstance(bridge_contract, dict) else {}
    bridge_action_decision = bridge_payload.get("action_decision") if isinstance(bridge_payload, dict) else {}
    controlled_gate = click.get("controlled_live_click_gate") if isinstance(click, dict) else {}
    roi_guard = click.get("action_button_slot_roi_guard") if isinstance(click, dict) else {}

    solver_decision_id = str(solver.get("decision_id") or "") if isinstance(solver, dict) else ""
    bridge_decision_id = str(bridge_action_decision.get("decision_id") or "") if isinstance(bridge_action_decision, dict) else ""
    target_sequence = click.get("target_sequence") if isinstance(click, dict) else []
    click_points = click.get("click_points") if isinstance(click, dict) else []

    checks = {
        "bridge_status_ok": bridge_contract.get("status") == "ok",
        "bridge_action_decision_present": isinstance(bridge_action_decision, dict) and bool(bridge_action_decision),
        "bridge_decision_id_present": bool(bridge_decision_id),
        "solver_source_solver_preflop": solver.get("source") == "PokerVision_Solver_Preflop",
        "solver_status_ok": solver.get("status") == "ok",
        "solver_decision_id_present": bool(solver_decision_id),
        "solver_decision_id_matches_bridge": bool(solver_decision_id) and solver_decision_id == bridge_decision_id,
        "solver_decision_id_not_stub": not solver_decision_id.startswith("v12_stub_"),
        "solver_decision_id_not_fallback": not solver_decision_id.startswith("v12_fallback_"),
        "runtime_selected_solver_bridge": (
            (solver.get("runtime_source_selection") or {}).get("selected_source") == "Solver_Preflop_Bridge"
        ),
        "runtime_selection_reason_v23": (
            (solver.get("runtime_source_selection") or {}).get("reason") == "v23_solver_preflop_selected_for_live_runtime"
        ),
        "raw_raise_family_action": str(solver.get("raw_action") or "") in {
            "raise",
            "open_raise",
            "iso_raise",
            "3bet",
            "4bet",
            "5bet",
            "jam",
            "all_in",
        },
        "raise_family_mapped_to_bet_raise": solver.get("action") == "bet_raise",
        "fake_action_button_used": action_buttons.get("status") == "ok" and action_buttons.get("raw_detection_count") == 9,
        "click_status_dry_run": click.get("status") == "dry_run",
        "click_decision_id_matches_solver": click.get("decision_id") == solver_decision_id,
        "target_sequence_built": isinstance(target_sequence, list) and len(target_sequence) >= 1,
        "click_points_built": isinstance(click_points, list) and len(click_points) == len(target_sequence),
        "slot_roi_guard_ok": isinstance(roi_guard, dict) and roi_guard.get("ok") is True,
        "controlled_gate_dry_run_allowed": (
            isinstance(controlled_gate, dict)
            and controlled_gate.get("status") == "CONTROLLED_LIVE_CLICK_GATE_DRY_RUN_ALLOWED"
            and controlled_gate.get("scope_passed") is True
        ),
        "guard_passed": click.get("guard_passed") is True,
        "dry_run_true": click.get("dry_run") is True,
        "real_click_disabled": click.get("real_click_enabled") is False,
        "physical_click_executed_false": click.get("status") != "clicked",
    }

    report = {
        "schema": SCHEMA,
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "out_dir": str(OUT_DIR),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "case": {
            "name": "unopened_btn_aa_openraise_fake_action_button_dry_run",
            "table_id": table_id,
            "frame_id": clear_state.get("frame_id"),
            "bridge_status": bridge_contract.get("status"),
            "bridge_raw_action": bridge_contract.get("raw_action"),
            "bridge_click_sequence": bridge_contract.get("click_sequence"),
            "runtime_solver_action": solver.get("action"),
            "runtime_solver_raw_action": solver.get("raw_action"),
            "runtime_solver_source": solver.get("source"),
            "runtime_solver_status": solver.get("status"),
            "runtime_decision_id": solver_decision_id,
            "click_status": click.get("status"),
            "target_sequence": target_sequence,
            "click_points_count": len(click_points) if isinstance(click_points, list) else 0,
        },
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
