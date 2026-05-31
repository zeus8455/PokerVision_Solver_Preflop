r"""
runtime/action_click_stub.py

PokerVision Core V3.1 — protected real/dry-run click runtime with controlled live one-click gate.

Builds an Action_Button click plan and, when config allows, executes it through
human-like mouse movement with static-mouse wait, slot guard and anti-repeat.
"""

from __future__ import annotations

import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from config import (
    V11_CLICK_ANTI_REPEAT_SEC,
    V11_CLICK_DRY_RUN,
    V11_CLICK_REQUIRE_ACTIVE,
    V11_CLICK_REQUIRE_BUTTON_DETECTION,
    V11_CLICK_SAFE_INNER_BBOX_RATIO,
    V11_CLICK_SLOT_GUARD_ENABLED,
    V11_CLICK_STUB_ENABLED,
    V11_REAL_MOUSE_CLICK_ENABLED,
    V31_CONTROLLED_LIVE_CLICK_ALLOWED_ACTIONS,
    V31_CONTROLLED_LIVE_CLICK_ALLOWED_BUTTONS,
    V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS,
    V31_CONTROLLED_LIVE_CLICK_ENV_VALUE,
    V31_CONTROLLED_LIVE_CLICK_ENV_VAR,
    V31_CONTROLLED_LIVE_CLICK_GATE_ENABLED,
    V31_CONTROLLED_LIVE_CLICK_GATE_SCHEMA_VERSION,
    V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN,
    V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN_ENV_VAR,
    V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED,
    V31_CONTROLLED_LIVE_CLICK_REQUIRE_ENV_CONFIRM,
    V31_CONTROLLED_LIVE_CLICK_REQUIRE_FULL_SCREEN_BLOCKED,
    V31_CONTROLLED_LIVE_CLICK_REQUIRE_INSIDE_SLOT,
    V31_CONTROLLED_LIVE_CLICK_REQUIRE_ROI_GUARD_OK,
    V31_CONTROLLED_LIVE_CLICK_TABLE_ID,
    V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR,
    V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR,
    get_v31_controlled_live_click_target_table_id,
    get_v31_controlled_live_click_target_table_ids,
)
from logic.action_button_policy import build_fallback_button_sequences
from logic.premium_fold_guard import evaluate_premium_fold_guard
from logic.action_button_slot_roi_guard import (
    ActionButtonSlotRoiGuardRequest,
    validate_action_button_slot_roi_guard,
)
from runtime.mouse_human_runtime import execute_click_points_human_like


_EXECUTED_DECISION_AT: Dict[str, float] = {}
_CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS: set[str] = set()
_CONTROLLED_LIVE_CLICK_EXECUTED_COUNT = 0


def _normalise_action(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace("/", "_")


def _is_raise_or_size_button(value: Any) -> bool:
    return str(value or "").strip() in {"33%", "50%", "70%", "98%", "Bet", "Raise", "Bet/Raise"}


def _env_confirmed() -> bool:
    return os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_ENV_VAR), "") == str(V31_CONTROLLED_LIVE_CLICK_ENV_VALUE)


def _configured_controlled_live_click_table_ids() -> List[str]:
    """Return effective controlled live-click target table set.

    V4.7 supported one target table via POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_ID.
    V5.4 adds a narrow comma-separated table set via
    POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS, while keeping the old single-table
    env override backward-compatible.
    """
    allowed = {str(x) for x in V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS}
    try:
        configured = [str(x) for x in get_v31_controlled_live_click_target_table_ids()]
    except Exception:
        multi_raw = os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR), "")
        configured = [item.strip() for item in multi_raw.split(",") if item.strip() in allowed]
        if not configured:
            legacy = os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR), "")
            if legacy in allowed:
                configured = [legacy]
    if not configured:
        configured = [str(get_v31_controlled_live_click_target_table_id())]
    safe: List[str] = []
    for table_id in configured:
        if table_id in allowed and table_id not in safe:
            safe.append(table_id)
    return safe or [str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID)]


def _configured_controlled_live_click_table_id() -> str:
    """Backward-compatible first configured controlled live-click target table."""
    return _configured_controlled_live_click_table_ids()[0]


def _build_controlled_live_click_gate_report(
    *,
    solver_decision: Dict[str, Any],
    selected_sequence: List[str],
    click_points: List[Dict[str, Any]],
    roi_guard_report: Dict[str, Any],
    dry_run: bool,
    real_click_enabled: bool,
) -> Dict[str, Any]:
    """V3.1 final runtime gate before any physical Action_Button click."""

    global _CONTROLLED_LIVE_CLICK_EXECUTED_COUNT

    table_id = str(solver_decision.get("table_id") or "")
    action = _normalise_action(solver_decision.get("action"))
    decision_id = str(solver_decision.get("decision_id") or "").strip()
    solver_source = str(solver_decision.get("source") or "")
    solver_status = str(solver_decision.get("status") or "")
    target_button = str(selected_sequence[0]) if selected_sequence else ""
    wants_real_click = bool(real_click_enabled) and not bool(dry_run)
    configured_table_ids = _configured_controlled_live_click_table_ids()
    configured_table_id = configured_table_ids[0]
    blockers: List[str] = []

    if not V31_CONTROLLED_LIVE_CLICK_GATE_ENABLED:
        status = "CONTROLLED_LIVE_CLICK_GATE_DISABLED"
        scope_passed = True
    else:
        if wants_real_click:
            if table_id not in configured_table_ids:
                blockers.append("controlled_live_click_wrong_table_id")
            if action not in {str(x) for x in V31_CONTROLLED_LIVE_CLICK_ALLOWED_ACTIONS}:
                blockers.append("controlled_live_click_action_not_allowed")
            if target_button not in {str(x) for x in V31_CONTROLLED_LIVE_CLICK_ALLOWED_BUTTONS}:
                blockers.append("controlled_live_click_button_not_allowed")
            if any(_is_raise_or_size_button(x) for x in selected_sequence) and not bool(V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED):
                blockers.append("controlled_live_click_raise_or_size_blocked")
            if bool(V31_CONTROLLED_LIVE_CLICK_REQUIRE_ROI_GUARD_OK) and not bool(roi_guard_report.get("ok")):
                blockers.append("controlled_live_click_roi_guard_not_ok")
            if bool(V31_CONTROLLED_LIVE_CLICK_REQUIRE_FULL_SCREEN_BLOCKED) and not bool(roi_guard_report.get("full_screen_search_blocked")):
                blockers.append("controlled_live_click_full_screen_search_not_blocked")
            if bool(V31_CONTROLLED_LIVE_CLICK_REQUIRE_INSIDE_SLOT) and not all(bool(p.get("inside_slot_bbox")) for p in click_points):
                blockers.append("controlled_live_click_point_outside_slot")
            if bool(V31_CONTROLLED_LIVE_CLICK_REQUIRE_ENV_CONFIRM) and not _env_confirmed():
                blockers.append("controlled_live_click_env_confirmation_missing")
            if solver_source != "PokerVision_Solver_Preflop":
                blockers.append("controlled_live_click_solver_source_not_solver_preflop")
            if solver_status != "ok":
                blockers.append("controlled_live_click_solver_status_not_ok")
            if decision_id.startswith("v12_stub_"):
                blockers.append("controlled_live_click_stub_decision_blocked")
            if decision_id.startswith("v12_fallback_"):
                blockers.append("controlled_live_click_fallback_decision_blocked")
            if not decision_id:
                blockers.append("controlled_live_click_missing_decision_id")
            if decision_id in _CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS:
                blockers.append("controlled_live_click_decision_already_executed")
            max_clicks_per_run = int(V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN)
            if max_clicks_per_run > 0 and _CONTROLLED_LIVE_CLICK_EXECUTED_COUNT >= max_clicks_per_run:
                blockers.append("controlled_live_click_max_clicks_reached")

        scope_passed = not blockers
        status = "CONTROLLED_LIVE_CLICK_GATE_PASSED" if scope_passed else "CONTROLLED_LIVE_CLICK_GATE_BLOCKED"
        if not wants_real_click:
            status = "CONTROLLED_LIVE_CLICK_GATE_DRY_RUN_ALLOWED"
            scope_passed = True

    return {
        "schema_version": str(V31_CONTROLLED_LIVE_CLICK_GATE_SCHEMA_VERSION),
        "feature_version": "v3_1_controlled_live_one_click",
        "enabled": bool(V31_CONTROLLED_LIVE_CLICK_GATE_ENABLED),
        "status": status,
        "scope_passed": bool(scope_passed),
        "blockers": blockers,
        "table_id": table_id,
        "configured_table_id": configured_table_id,
        "configured_table_ids": list(configured_table_ids),
        "configured_default_table_id": str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID),
        "allowed_table_ids": [str(x) for x in V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS],
        "table_id_env_var": str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR),
        "table_id_env_value": os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR), ""),
        "table_ids_env_var": str(V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR),
        "table_ids_env_value": os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR), ""),
        "action": action,
        "target_sequence": list(selected_sequence),
        "target_button_class": target_button,
        "decision_id": decision_id,
        "solver_source": solver_source,
        "solver_status": solver_status,
        "dry_run": bool(dry_run),
        "real_click_enabled": bool(real_click_enabled),
        "wants_real_click": bool(wants_real_click),
        "env_var": str(V31_CONTROLLED_LIVE_CLICK_ENV_VAR),
        "env_confirmed": _env_confirmed(),
        "max_clicks_per_run": int(V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN),
        "executed_clicks_count": int(_CONTROLLED_LIVE_CLICK_EXECUTED_COUNT),
        "allowed_actions": [str(x) for x in V31_CONTROLLED_LIVE_CLICK_ALLOWED_ACTIONS],
        "allowed_buttons": [str(x) for x in V31_CONTROLLED_LIVE_CLICK_ALLOWED_BUTTONS],
        "raise_branch_enabled": bool(V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED),
        "roi_guard_ok": bool(roi_guard_report.get("ok")),
        "full_screen_search_blocked": bool(roi_guard_report.get("full_screen_search_blocked")),
        "click_points_count": len(click_points),
        "all_click_points_inside_slot": all(bool(p.get("inside_slot_bbox")) for p in click_points),
    }


def _record_controlled_live_click_success(decision_id: Any) -> Dict[str, Any]:
    global _CONTROLLED_LIVE_CLICK_EXECUTED_COUNT
    clean_id = str(decision_id or "").strip()
    if clean_id and clean_id not in _CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS:
        _CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS.add(clean_id)
        _CONTROLLED_LIVE_CLICK_EXECUTED_COUNT += 1
    return {
        "schema_version": str(V31_CONTROLLED_LIVE_CLICK_GATE_SCHEMA_VERSION),
        "status": "CONTROLLED_LIVE_CLICK_SUCCESS_RECORDED",
        "decision_id": clean_id,
        "executed_clicks_count": int(_CONTROLLED_LIVE_CLICK_EXECUTED_COUNT),
        "max_clicks_per_run": int(V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN),
    }


def _now() -> float:
    return time.time()


def _bbox_center_inside_safe_zone(bbox_xyxy: List[int], safe_ratio: float) -> Tuple[int, int]:
    x1, y1, x2, y2 = [int(v) for v in bbox_xyxy]
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)
    inset_x = int(w * safe_ratio)
    inset_y = int(h * safe_ratio)
    safe_x1 = min(x2 - 1, x1 + inset_x)
    safe_x2 = max(safe_x1 + 1, x2 - inset_x)
    safe_y1 = min(y2 - 1, y1 + inset_y)
    safe_y2 = max(safe_y1 + 1, y2 - inset_y)
    return random.randint(safe_x1, safe_x2 - 1), random.randint(safe_y1, safe_y2 - 1)


def _local_point_to_global(point: Tuple[int, int], slot_bbox: Any) -> Tuple[int, int]:
    local_x, local_y = point
    return int(slot_bbox.x1) + local_x, int(slot_bbox.y1) + local_y


def _point_inside_slot(global_point: Tuple[int, int], slot_bbox: Any) -> bool:
    x, y = global_point
    return int(slot_bbox.x1) <= x <= int(slot_bbox.x2) and int(slot_bbox.y1) <= y <= int(slot_bbox.y2)


def _find_first_available_sequence(
    sequences: List[List[str]],
    best_by_class: Dict[str, Dict[str, Any]],
) -> Optional[List[str]]:
    for sequence in sequences:
        if all(class_name in best_by_class for class_name in sequence):
            return sequence
    return None


def _build_click_points(sequence: List[str], best_by_class: Dict[str, Dict[str, Any]], slot_bbox: Any) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for class_name in sequence:
        detection = best_by_class[class_name]
        local_bbox = [int(v) for v in detection["bbox_xyxy"]]
        local_point = _bbox_center_inside_safe_zone(local_bbox, V11_CLICK_SAFE_INNER_BBOX_RATIO)
        global_point = _local_point_to_global(local_point, slot_bbox)
        points.append(
            {
                "class_name": class_name,
                "confidence": detection.get("confidence"),
                "local_bbox_xyxy": local_bbox,
                "local_click_point": {"x": local_point[0], "y": local_point[1]},
                "global_click_point": {"x": global_point[0], "y": global_point[1]},
                "inside_slot_bbox": _point_inside_slot(global_point, slot_bbox),
            }
        )
    return points



def _slot_bbox_tuple(slot_bbox: Any) -> Tuple[float, float, float, float]:
    return (
        float(slot_bbox.x1),
        float(slot_bbox.y1),
        float(slot_bbox.x2),
        float(slot_bbox.y2),
    )


def _slot_roi_size(slot_bbox: Any) -> Tuple[float, float]:
    x1, y1, x2, y2 = _slot_bbox_tuple(slot_bbox)
    return max(1.0, x2 - x1), max(1.0, y2 - y1)


def _global_click_point_tuple(point_payload: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    raw = point_payload.get("global_click_point") if isinstance(point_payload, dict) else None
    if not isinstance(raw, dict):
        return None
    try:
        return float(raw["x"]), float(raw["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _build_action_button_slot_roi_guard_report(
    *,
    table_id: Any,
    slot_bbox: Any,
    click_points: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build V2.6 runtime audit for Action_Button_Detector table-slot ROI discipline."""

    slot_bbox_tuple = _slot_bbox_tuple(slot_bbox)
    roi_size = _slot_roi_size(slot_bbox)
    per_button: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []

    if not click_points:
        request = ActionButtonSlotRoiGuardRequest(
            table_id=str(table_id or "unknown_table"),
            detector_input_scope="table_roi",
            slot_bbox=slot_bbox_tuple,
            roi_size=roi_size,
            local_bbox_xyxy=None,
            click_point_global=None,
            source="Action_Button_Detector/runtime_action_button",
        )
        audit = validate_action_button_slot_roi_guard(request)
        per_button.append(audit)
        warnings.extend(str(item) for item in audit.get("warnings", []) if item not in warnings)
        errors.extend(str(item) for item in audit.get("errors", []) if item not in errors)
    else:
        for point in click_points:
            local_bbox = point.get("local_bbox_xyxy") if isinstance(point, dict) else None
            click_xy = _global_click_point_tuple(point if isinstance(point, dict) else {})
            request = ActionButtonSlotRoiGuardRequest(
                table_id=str(table_id or "unknown_table"),
                detector_input_scope="table_roi",
                slot_bbox=slot_bbox_tuple,
                roi_size=roi_size,
                local_bbox_xyxy=local_bbox,
                click_point_global=click_xy,
                source="Action_Button_Detector/runtime_action_button",
            )
            audit = validate_action_button_slot_roi_guard(request)
            audit["button_class"] = str(point.get("class_name") or "") if isinstance(point, dict) else ""
            per_button.append(audit)
            for item in audit.get("errors", []):
                text = str(item)
                if text not in errors:
                    errors.append(text)
            for item in audit.get("warnings", []):
                text = str(item)
                if text not in warnings:
                    warnings.append(text)

    ok = not errors and all(bool(item.get("ok")) for item in per_button)
    return {
        "schema_version": "action_button_slot_roi_runtime_audit_v2_6",
        "audit_exposure_version": "v2_7_dark_json_exposure",
        "ok": ok,
        "status": "ACTION_BUTTON_SLOT_ROI_RUNTIME_AUDIT_OK" if ok else "ACTION_BUTTON_SLOT_ROI_RUNTIME_AUDIT_BLOCKED",
        "table_id": str(table_id or "unknown_table"),
        "detector_input_scope": "table_roi",
        "full_screen_search_blocked": True,
        "errors": errors,
        "warnings": warnings,
        "slot_bbox": {
            "x1": slot_bbox_tuple[0],
            "y1": slot_bbox_tuple[1],
            "x2": slot_bbox_tuple[2],
            "y2": slot_bbox_tuple[3],
        },
        "roi_size": {"w": roi_size[0], "h": roi_size[1]},
        "click_points_count": len(click_points),
        "per_button": per_button,
    }


def build_and_maybe_execute_click_plan(
    *,
    solver_decision: Dict[str, Any],
    action_button_result: Any,
    slot: Any,
    active_confirmed: bool,
) -> Dict[str, Any]:
    """Build safe click plan from solver decision and normalized button detections."""
    started_at = time.perf_counter()
    decision_id = solver_decision.get("decision_id")

    report: Dict[str, Any] = {
        "status": "skipped",
        "decision_id": decision_id,
        "table_id": solver_decision.get("table_id"),
        "hand_id": solver_decision.get("hand_id"),
        "frame_name": solver_decision.get("frame_name"),
        "action": solver_decision.get("action"),
        "size_pct": solver_decision.get("size_pct"),
        # V2.37: expose Solver_Preflop lineage directly in click_result/runtime report.
        # This keeps Final Clear/JSON_Complete audits readable without digging into
        # nested solver_preflop_bridge_contract payloads.
        "solver_source": solver_decision.get("source"),
        "solver_status": solver_decision.get("status"),
        "solver_raw_action": (solver_decision.get("solver_raw_action") or solver_decision.get("raw_action") or locals().get("raw_action")),  # V237_CLICK_ORIGINAL_SOLVER_RAW_ACTION_LINEAGE
        "solver_engine_action": solver_decision.get("engine_action"),
        "solver_fingerprint": solver_decision.get("solver_fingerprint"),
        "source_frame_id": solver_decision.get("source_frame_id"),
        "solver_click_sequence": list(solver_decision.get("click_sequence") or []),
        # V2.44: expose premium fold guard context in every click_result.
        "hero_hand": list(solver_decision.get("hero_hand") or []),
        "hand_class": solver_decision.get("hand_class"),
        "node_type": solver_decision.get("node_type"),
        "safe_fallback_used": bool(solver_decision.get("safe_fallback_used")),
        "premium_fold_guard": None,
        "target_sequence": [],
        "click_points": [],
        "guard_passed": False,
        "dry_run": bool(V11_CLICK_DRY_RUN),
        "real_click_enabled": bool(V11_REAL_MOUSE_CLICK_ENABLED),
        "message": None,
        "processing_time_ms": 0,
        "action_button_slot_roi_guard": None,
        "controlled_live_click_gate": None,
    }

    def finish(status: str, message: str) -> Dict[str, Any]:
        if report.get("action_button_slot_roi_guard") is None:
            try:
                report["action_button_slot_roi_guard"] = _build_action_button_slot_roi_guard_report(
                    table_id=solver_decision.get("table_id"),
                    slot_bbox=slot.bbox,
                    click_points=report.get("click_points") if isinstance(report.get("click_points"), list) else [],
                )
            except Exception as exc:
                report["action_button_slot_roi_guard"] = {
                    "schema_version": "action_button_slot_roi_runtime_audit_v2_6",
                    "audit_exposure_version": "v2_7_dark_json_exposure",
                    "ok": False,
                    "status": "ACTION_BUTTON_SLOT_ROI_RUNTIME_AUDIT_ERROR",
                    "table_id": str(solver_decision.get("table_id") or "unknown_table"),
                    "detector_input_scope": "table_roi",
                    "full_screen_search_blocked": True,
                    "errors": [f"roi_guard_runtime_error: {exc}"],
                    "warnings": [],
                    "click_points_count": 0,
                }

        # V3.1 audit must be visible on every real-click attempt, including
        # early blocked paths such as wrong table, missing button sequence, or
        # anti-repeat. Without this fallback Dark_JSON/tests can see
        # controlled_live_click_gate=None even though the gate was the relevant
        # safety contract for the blocked physical click.
        if report.get("controlled_live_click_gate") is None:
            try:
                report["controlled_live_click_gate"] = _build_controlled_live_click_gate_report(
                    solver_decision=solver_decision,
                    selected_sequence=(
                        report.get("target_sequence") if isinstance(report.get("target_sequence"), list) else []
                    ),
                    click_points=(
                        report.get("click_points") if isinstance(report.get("click_points"), list) else []
                    ),
                    roi_guard_report=(
                        report.get("action_button_slot_roi_guard")
                        if isinstance(report.get("action_button_slot_roi_guard"), dict)
                        else {}
                    ),
                    dry_run=bool(V11_CLICK_DRY_RUN),
                    real_click_enabled=bool(V11_REAL_MOUSE_CLICK_ENABLED),
                )
            except Exception as exc:
                report["controlled_live_click_gate"] = {
                    "schema_version": str(V31_CONTROLLED_LIVE_CLICK_GATE_SCHEMA_VERSION),
                    "feature_version": "v3_1_controlled_live_one_click",
                    "enabled": bool(V31_CONTROLLED_LIVE_CLICK_GATE_ENABLED),
                    "status": "CONTROLLED_LIVE_CLICK_GATE_ERROR",
                    "scope_passed": False,
                    "blockers": [f"controlled_live_click_gate_runtime_error:{type(exc).__name__}:{exc}"],
                    "table_id": str(solver_decision.get("table_id") or ""),
                    "configured_table_id": _configured_controlled_live_click_table_id(),
                    "configured_table_ids": _configured_controlled_live_click_table_ids(),
                    "configured_default_table_id": str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID),
                    "allowed_table_ids": [str(x) for x in V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS],
                    "table_id_env_var": str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR),
                    "table_id_env_value": os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR), ""),
                    "table_ids_env_var": str(V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR),
                    "table_ids_env_value": os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR), ""),
                    "dry_run": bool(V11_CLICK_DRY_RUN),
                    "real_click_enabled": bool(V11_REAL_MOUSE_CLICK_ENABLED),
                    "wants_real_click": bool(V11_REAL_MOUSE_CLICK_ENABLED) and not bool(V11_CLICK_DRY_RUN),
                }

        report["status"] = status
        report["message"] = message
        report["processing_time_ms"] = int((time.perf_counter() - started_at) * 1000)
        return report

    if not V11_CLICK_STUB_ENABLED:
        return finish("skipped", "V1.1 click stub is disabled by config.")

    if V11_CLICK_REQUIRE_ACTIVE and not active_confirmed:
        return finish("skipped", "Active is not confirmed; click skipped.")

    if not decision_id:
        return finish("blocked", "Missing decision_id; anti-repeat cannot be enforced.")

    previous_at = _EXECUTED_DECISION_AT.get(str(decision_id))
    if previous_at is not None and (_now() - previous_at) < V11_CLICK_ANTI_REPEAT_SEC:
        return finish("blocked", "Decision was already executed recently; anti-repeat blocked click.")

    best_by_class = getattr(action_button_result, "best_by_class", None)
    if best_by_class is None and isinstance(action_button_result, dict):
        best_by_class = action_button_result.get("best_by_class")
    best_by_class = best_by_class or {}

    if V11_CLICK_REQUIRE_BUTTON_DETECTION and not best_by_class:
        return finish("blocked", "No action button detections available.")

    # V2.44: top-layer safety override before any FOLD click is selected.
    premium_fold_guard = evaluate_premium_fold_guard(
        solver_decision=solver_decision,
        available_buttons=best_by_class.keys(),
    )
    report["premium_fold_guard"] = premium_fold_guard

    if bool(premium_fold_guard.get("active")):
        sequences = [list(seq) for seq in (premium_fold_guard.get("target_sequences") or [])]
    else:
        try:
            sequences = build_fallback_button_sequences(
                solver_decision.get("action"),
                solver_decision.get("size_pct"),
            )
        except Exception as exc:
            return finish("error", f"Invalid solver decision: {exc}")

    selected_sequence = _find_first_available_sequence(sequences, best_by_class)
    if not selected_sequence:
        if bool(premium_fold_guard.get("active")):
            return finish(
                "blocked",
                str(
                    premium_fold_guard.get("message")
                    or "Premium fold guard blocked suspicious premium fold; no Raise/Call sequence available."
                ),
            )
        return finish("blocked", f"Required action button sequence not found. Tried: {sequences}")

    report["target_sequence"] = selected_sequence
    click_points = _build_click_points(selected_sequence, best_by_class, slot.bbox)
    report["click_points"] = click_points

    roi_guard_report = _build_action_button_slot_roi_guard_report(
        table_id=solver_decision.get("table_id"),
        slot_bbox=slot.bbox,
        click_points=click_points,
    )
    report["action_button_slot_roi_guard"] = roi_guard_report
    if not bool(roi_guard_report.get("ok")):
        return finish("blocked", "Action_Button_Detector slot ROI guard blocked this click plan.")

    if V11_CLICK_SLOT_GUARD_ENABLED and not all(point["inside_slot_bbox"] for point in click_points):
        return finish("blocked", "One or more click points are outside current slot_bbox.")

    report["guard_passed"] = True

    controlled_live_click_gate = _build_controlled_live_click_gate_report(
        solver_decision=solver_decision,
        selected_sequence=selected_sequence,
        click_points=click_points,
        roi_guard_report=roi_guard_report,
        dry_run=bool(V11_CLICK_DRY_RUN),
        real_click_enabled=bool(V11_REAL_MOUSE_CLICK_ENABLED),
    )
    report["controlled_live_click_gate"] = controlled_live_click_gate

    if not bool(controlled_live_click_gate.get("scope_passed")):
        return finish("blocked", "Controlled live one-click gate blocked this physical click plan.")

    if V11_CLICK_DRY_RUN or not V11_REAL_MOUSE_CLICK_ENABLED:
        return finish("dry_run", "Dry-run target selected; physical click disabled.")

    try:
        mouse_report = execute_click_points_human_like(click_points)
        report["mouse"] = mouse_report
        _EXECUTED_DECISION_AT[str(decision_id)] = _now()
        report["controlled_live_click_success"] = _record_controlled_live_click_success(decision_id)
        return finish("clicked", "Physical click executed with human-like mouse runtime after V3.1 controlled live-click gate.")
    except Exception as exc:
        return finish("error", f"Mouse execution failed: {exc}")
