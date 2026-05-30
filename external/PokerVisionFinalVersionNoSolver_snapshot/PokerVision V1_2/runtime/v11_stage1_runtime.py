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
from config import (
    V09_REAL_CLICK_MASTER_ARMED,
    V11_REAL_MOUSE_CLICK_ENABLED,
    V11_CLICK_DRY_RUN,
)
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


def _normalise_solver_preflop_runtime_action(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace("/", "_")
    if raw in {"fold"}:
        return "fold"
    if raw in {"call"}:
        return "call"
    if raw in {"check"}:
        return "check"
    if raw in {"check_fold", "checkfold"}:
        return "check_fold"
    if raw in {"raise", "bet", "bet_raise", "open_raise", "iso_raise", "3bet", "4bet", "5bet", "jam", "all_in"}:
        return "bet_raise"
    return raw


def _extract_solver_preflop_decision_from_state(
    *,
    full_state: Dict[str, Any],
    solver_payload: Dict[str, Any],
    solver_payload_path: Path,
) -> Optional[Dict[str, Any]]:
    contract = full_state.get("solver_preflop_bridge_contract")
    if not isinstance(contract, dict):
        return None

    # V2.31: accept Solver_Preflop fallback bridge when action_decision is available.
    #
    # Live failure fixed here:
    # - display/runtime source selection can correctly choose Solver_Preflop_Bridge with
    #   solver_action_decision_available=True while the bridge contract status is "fallback"
    #   for conservative unsupported nodes such as multi_raise_unknown.
    # - The previous extractor accepted only status == "ok", returned None for fallback,
    #   and run_v11_stage1_runtime then built the legacy v12_stub_* decision.
    # - Real-click is explicitly blocked for legacy v12 stubs, so the poker Action_Button
    #   click branch never executed even though Solver_Preflop had a usable safe fold/check/call decision.
    contract_status = str(contract.get("status") or "")
    if contract_status not in {"ok", "fallback"}:
        return None

    bridge_payload = contract.get("bridge_payload")
    if not isinstance(bridge_payload, dict):
        return None

    action_decision = bridge_payload.get("action_decision")
    # V237_ORIGINAL_SOLVER_RAW_ACTION_LINEAGE: preserve semantic Solver_Preflop raw action.
    if isinstance(action_decision, dict):
        original_solver_raw_action = (
            bridge_payload.get('raw_action')
            or bridge_payload.get('solver_raw_action')
            or (action_decision.get('decision_context') or {}).get('solver_raw_action')
            or action_decision.get('raw_action')
            or action_decision.get('action')
        )
        action_decision['solver_raw_action'] = original_solver_raw_action
        action_decision.setdefault('decision_context', {})['solver_raw_action'] = original_solver_raw_action
    else:
        original_solver_raw_action = None
    if not isinstance(action_decision, dict):
        return None

    raw_action = (
        action_decision.get("action")
        or action_decision.get("engine_action")
        or action_decision.get("raw_action")
        or contract.get("engine_action")
        or contract.get("raw_action")
    )
    action = _normalise_solver_preflop_runtime_action(raw_action)

    size_pct = (
        action_decision.get("size_pct")
        or action_decision.get("raise_size_pct")
        or action_decision.get("button_pct")
    )

    if size_pct is None:
        size_policy = action_decision.get("size_policy")
        if isinstance(size_policy, dict):
            size_pct = (
                size_policy.get("size_pct")
                or size_policy.get("raise_size_pct")
                or size_policy.get("button_pct")
            )

    runtime_candidate = contract.get("runtime_plan_candidate")
    if size_pct is None and isinstance(runtime_candidate, dict):
        target_sequence = runtime_candidate.get("target_sequence")
        if isinstance(target_sequence, list):
            for button in target_sequence:
                text = str(button).strip().replace("%", "")
                if text in {"33", "50", "70", "98"}:
                    size_pct = int(text)
                    break

    if action != "bet_raise":
        size_pct = None

    return {
        "status": "ok",
        "source": "PokerVision_Solver_Preflop",
        "decision_id": (
            action_decision.get("decision_id")
            or contract.get("decision_id")
            or bridge_payload.get("decision_id")
        ),
        "solver_fingerprint": (
            action_decision.get("solver_fingerprint")
            or contract.get("solver_fingerprint")
            or bridge_payload.get("solver_fingerprint")
        ),
        "table_id": solver_payload.get("table_id"),
        "hand_id": solver_payload.get("hand_id"),
        "frame_name": solver_payload.get("frame_name"),
        "action": action,
        "raw_action": original_solver_raw_action,
        "engine_action": action_decision.get("engine_action") or contract.get("engine_action"),
        "size_pct": size_pct,
        "reason": str(action_decision.get("reason") or "solver_preflop_bridge_live_runtime_source"),
        "json_path": str(solver_payload_path),
        "source_frame_id": action_decision.get("source_frame_id") or contract.get("source_frame_id"),
        "click_sequence": list(action_decision.get("click_sequence") or contract.get("click_sequence") or []),
        "total_pot_bb": _extract_total_pot_bb(full_state),
        "waited_sec": 0.0,
        "runtime_source_selection": {
            "selected_source": "Solver_Preflop_Bridge",
            "reason": "v23_solver_preflop_selected_for_live_runtime",
            "bridge_status": contract.get("status"),
        },
    }



# V2.37: compact runtime lineage exposed next to the v11 runtime result.
def _build_v237_runtime_lineage(
    *,
    solver_decision: Dict[str, Any],
    action_button_result: Any,
    click_report: Dict[str, Any],
) -> Dict[str, Any]:
    click = click_report if isinstance(click_report, dict) else {}
    gate = click.get("controlled_live_click_gate") if isinstance(click.get("controlled_live_click_gate"), dict) else {}
    detected_classes = getattr(action_button_result, "detected_classes", None)
    if detected_classes is None and isinstance(action_button_result, dict):
        detected_classes = action_button_result.get("detected_classes")
    return {
        "schema_version": "solver_preflop_v237_runtime_lineage_v1",
        "source": solver_decision.get("source"),
        "selected_source": (
            (solver_decision.get("runtime_source_selection") or {}).get("selected_source")
            if isinstance(solver_decision.get("runtime_source_selection"), dict)
            else None
        ),
        "bridge_status": (
            (solver_decision.get("runtime_source_selection") or {}).get("bridge_status")
            if isinstance(solver_decision.get("runtime_source_selection"), dict)
            else None
        ),
        "decision_id": solver_decision.get("decision_id"),
        "solver_fingerprint": solver_decision.get("solver_fingerprint"),
        "source_frame_id": solver_decision.get("source_frame_id"),
        "solver_raw_action": solver_decision.get("raw_action"),
        "solver_engine_action": solver_decision.get("engine_action"),
        "runtime_action": solver_decision.get("action"),
        "size_pct": solver_decision.get("size_pct"),
        "solver_click_sequence": list(solver_decision.get("click_sequence") or []),
        "click_status": click.get("status"),
        "click_completed": click.get("status") == "clicked" and bool(click.get("guard_passed")),
        "target_sequence": list(click.get("target_sequence") or []),
        "guard_passed": bool(click.get("guard_passed")),
        "controlled_gate_status": gate.get("status"),
        "controlled_gate_blockers": list(gate.get("blockers") or []),
        "action_button_detected_classes": list(detected_classes or []),
    }


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

    solver_decision = _extract_solver_preflop_decision_from_state(
        full_state=full_state,
        solver_payload=solver_payload,
        solver_payload_path=solver_payload_path,
    )
    if solver_decision is None:
        solver_decision = build_solver_stub_decision(solver_payload, json_path=str(solver_payload_path))
        solver_decision = _apply_solver_timeout_fallback(solver_payload, solver_decision, full_state)

    solver_decision.setdefault("total_pot_bb", _extract_total_pot_bb(full_state))
    solver_decision.setdefault("waited_sec", None)

    real_click_mode = (
        bool(V09_REAL_CLICK_MASTER_ARMED)
        and bool(V11_REAL_MOUSE_CLICK_ENABLED)
        and V11_CLICK_DRY_RUN is False
    )
    stub_decision_id = str(solver_decision.get("decision_id") or "")
    stub_status = str(solver_decision.get("status") or "")
    if real_click_mode and (stub_status == "stub" or stub_decision_id.startswith("v12_stub_")):
        update_table_runtime_status(
            table_id,
            solver_status="blocked_stub_real_click",
            solver_action=solver_decision.get("action"),
            solver_size_pct=solver_decision.get("size_pct"),
            click_status="blocked",
        )
        return {
            "schema_version": "1.1-runtime",
            "table_id": table_id,
            "hand_id": hand_id,
            "frame_name": frame_name,
            "json": {"status": json_status, "processing_time_ms": json_time_ms},
            "payload": {"status": "saved", "path": str(solver_payload_path)},
            "solver": {
                **dict(solver_decision),
                "status": "blocked_stub_real_click",
                "blocked": True,
                "block_reason": "v21_stub_decision_cannot_execute_real_click",
            },
            "action_buttons": {"status": "skipped", "detected_classes": []},
            "click": {
                "status": "blocked",
                "target_sequence": [],
                "click_completed": False,
                "guard_passed": False,
                "reason": "v21_stub_decision_cannot_execute_real_click",
                "message": "Real-click runtime blocked because selected solver decision is the legacy v12 stub.",
            },
        }

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
        "runtime_lineage": _build_v237_runtime_lineage(
            solver_decision=solver_decision,
            action_button_result=action_button_result,
            click_report=click_report,
        ),
        "click": click_report,
    }
