r"""
runtime/v11_stage1_runtime.py

PokerVision Core V1.2 — action-button orchestrator with solver fallback contract.

Current contract:
- build and save the compact solver payload JSON;
- run the temporary solver stub;
- run Action_Button_Detector;
- build a click plan / dry-run result;
- return runtime data to the caller.

Important:
- this module no longer writes separate _runtime/*_click_report.json files;
- the caller embeds a compact summary into the main table-state JSON.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

from config import (
    V12_BIG_POT_EXTRA_WAIT_SEC,
    V12_BIG_POT_THRESHOLD_BB,
    V12_SOLVER_FALLBACK_ACTION,
    V12_SOLVER_FALLBACK_SIZE_PCT,
    V12_SOLVER_WAIT_TIMEOUT_SEC,
)
from pipeline.action_button_pipeline import run_action_button_pipeline
from runtime.action_click_stub import build_and_maybe_execute_click_plan
from runtime.solver_payload_builder import build_and_save_solver_payload
from runtime.solver_stub import build_solver_stub_decision
from runtime.table_overlay_status import update_table_runtime_status


def _extract_total_pot_bb(full_state: Dict[str, Any]) -> Optional[float]:
    try:
        block = (((full_state.get("table_structure") or {}).get("classes") or {}).get("Total_pot") or {})
        value = block.get("value")
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value).strip())
    except Exception:
        return None


def _solver_decision_has_action(decision: Dict[str, Any]) -> bool:
    return bool(decision.get("action")) and str(decision.get("status") or "") not in {"timeout", "error", "skipped"}


def _build_fallback_solver_decision(
    *,
    solver_payload: Dict[str, Any],
    reason: str,
    waited_sec: float,
    total_pot_bb: Optional[float],
) -> Dict[str, Any]:
    action = V12_SOLVER_FALLBACK_ACTION
    size_pct = V12_SOLVER_FALLBACK_SIZE_PCT
    table_id = solver_payload.get("table_id") or "unknown_table"
    hand_id = solver_payload.get("hand_id") or "unknown_hand"
    frame_name = solver_payload.get("frame_name") or "unknown_frame"
    action_event_id = solver_payload.get("action_event_id") or solver_payload.get("action_signature") or frame_name
    return {
        "status": "fallback",
        "source": "V1.2 solver timeout/failsafe fallback",
        "decision_id": f"v12_fallback_{table_id}_{hand_id}_{action_event_id}_{action}",
        "table_id": table_id,
        "hand_id": hand_id,
        "frame_name": frame_name,
        "action": action,
        "size_pct": size_pct,
        "reason": reason,
        "waited_sec": waited_sec,
        "total_pot_bb": total_pot_bb,
    }


def _apply_solver_timeout_fallback(solver_payload: Dict[str, Any], solver_decision: Dict[str, Any], full_state: Dict[str, Any]) -> Dict[str, Any]:
    if _solver_decision_has_action(solver_decision):
        solver_decision.setdefault("timeout_policy", {"applied": False})
        return solver_decision

    total_pot_bb = _extract_total_pot_bb(full_state)
    first_wait = float(V12_SOLVER_WAIT_TIMEOUT_SEC)
    extra_wait = 0.0
    if total_pot_bb is not None and total_pot_bb > float(V12_BIG_POT_THRESHOLD_BB):
        extra_wait = float(V12_BIG_POT_EXTRA_WAIT_SEC)
    waited = first_wait + extra_wait

    # Future real solver bridge should spend this time waiting for a decision.
    # The current stub returns immediately; this branch only runs when no valid decision exists.
    if waited > 0:
        time.sleep(min(waited, 0.25))

    if total_pot_bb is None:
        reason = f"No solver decision after {first_wait:.1f}s; total_pot unknown, fallback action selected."
    elif total_pot_bb <= float(V12_BIG_POT_THRESHOLD_BB):
        reason = f"No solver decision after {first_wait:.1f}s and Total_pot={total_pot_bb:g} <= {float(V12_BIG_POT_THRESHOLD_BB):g}; fallback action selected."
    else:
        reason = f"No solver decision after {first_wait:.1f}s + extra {extra_wait:.1f}s because Total_pot={total_pot_bb:g} > {float(V12_BIG_POT_THRESHOLD_BB):g}; fallback action selected."
    return _build_fallback_solver_decision(
        solver_payload=solver_payload,
        reason=reason,
        waited_sec=waited,
        total_pot_bb=total_pot_bb,
    )


def run_v11_stage1_runtime(
    *,
    full_state: Dict[str, Any],
    table_roi_image: Any,
    slot: Any,
    active_confirmed: bool,
    cycle_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Execute the safe V1.1 action-button branch.

    Real click execution is controlled by config flags and protected by slot guard, anti-repeat and human-like mouse runtime.
    No standalone runtime JSON report is written here.
    """
    table = full_state.get("table") or {}
    pipeline_meta = full_state.get("pipeline_meta") or {}
    table_id = str(table.get("table_id") or getattr(slot, "table_id", "unknown_table"))
    hand_id = table.get("hand_id")
    frame_name = str(table.get("frame_name") or "unknown_frame")
    json_time_ms = pipeline_meta.get("processing_time_ms") or table.get("processing_time_ms")
    runtime_status = str(pipeline_meta.get("status") or "warning")
    json_status = "compile" if runtime_status == "ok" else "warning"

    update_table_runtime_status(
        table_id,
        hand_id=hand_id,
        frame_name=frame_name,
        json_status=json_status,
        json_time_ms=json_time_ms,
        json_message=runtime_status,
        payload_status="process",
        solver_status="skipped",
        click_status="skipped",
    )

    try:
        solver_payload, solver_payload_path = build_and_save_solver_payload(full_state, cycle_dir=cycle_dir)
        update_table_runtime_status(
            table_id,
            payload_status="compile",
            payload_path=str(solver_payload_path),
            payload_message="solver payload created",
            solver_status="process",
        )
    except Exception as exc:
        update_table_runtime_status(
            table_id,
            payload_status="warning",
            payload_message=str(exc),
            solver_status="skipped",
            click_status="skipped",
        )
        return {
            "schema_version": "1.1-runtime",
            "table_id": table_id,
            "hand_id": hand_id,
            "frame_name": frame_name,
            "json": {"status": json_status, "processing_time_ms": json_time_ms},
            "payload": {"status": "error", "path": None, "message": str(exc)},
            "solver": {"status": "skipped"},
            "action_buttons": {"status": "skipped", "detected_classes": []},
            "click": {"status": "skipped", "target_sequence": [], "message": "Solver payload was not created."},
        }

    solver_decision = build_solver_stub_decision(solver_payload, json_path=str(solver_payload_path))
    solver_decision = _apply_solver_timeout_fallback(solver_payload, solver_decision, full_state)
    solver_decision.setdefault("total_pot_bb", _extract_total_pot_bb(full_state))
    solver_decision.setdefault("waited_sec", None)
    update_table_runtime_status(
        table_id,
        solver_status=str(solver_decision.get("status")),
        solver_action=solver_decision.get("action"),
        solver_size_pct=solver_decision.get("size_pct"),
        click_status="process",
    )

    action_button_result = run_action_button_pipeline(
        table_roi_image=table_roi_image,
        active_confirmed=active_confirmed,
    )

    click_report = build_and_maybe_execute_click_plan(
        solver_decision=solver_decision,
        action_button_result=action_button_result,
        slot=slot,
        active_confirmed=active_confirmed,
    )

    target_sequence = click_report.get("target_sequence") or []
    update_table_runtime_status(
        table_id,
        click_status=str(click_report.get("status")),
        click_target=" + ".join(target_sequence) if target_sequence else None,
        click_message=click_report.get("message"),
    )

    return {
        "schema_version": "1.1-runtime",
        "table_id": table_id,
        "hand_id": hand_id,
        "frame_name": frame_name,
        "json": {
            "status": json_status,
            "processing_time_ms": json_time_ms,
            "source_runtime_status": runtime_status,
        },
        "payload": {
            "status": "compile",
            "path": str(solver_payload_path),
        },
        "solver": solver_decision,
        "action_buttons": {
            "status": action_button_result.status,
            "detected_classes": action_button_result.detected_classes,
            "raw_detection_count": action_button_result.raw_detection_count,
            "processing_time_ms": action_button_result.processing_time_ms,
            "warnings": action_button_result.warnings,
            "errors": action_button_result.errors,
        },
        "click": click_report,
    }
