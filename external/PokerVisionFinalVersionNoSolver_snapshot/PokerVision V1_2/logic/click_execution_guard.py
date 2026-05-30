r"""
logic/click_execution_guard.py

PokerVision V0.9 — real-click readiness / click execution guard.

This module is deliberately isolated from pyautogui/mouse execution. It validates
whether a prepared Action_Runtime_Plan_JSON result is allowed to become a
click_result. In V0.9 default configuration, real physical clicks are blocked by
the master arm switch and live no-click mode; dry-run completion remains allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


Number = float | int
BBox = Tuple[float, float, float, float]
Point = Tuple[float, float]


_ALLOWED_ACTIONS = {'fold', 'call', 'check', 'check_fold', 'bet', 'raise', 'bet_raise'}


@dataclass(frozen=True)
class ClickGuardConfig:
    """Runtime-configurable guard switches."""

    enabled: bool = True
    real_click_master_armed: bool = False
    require_slot_boundary_guard: bool = True
    require_no_repeat_decision_guard: bool = True
    require_button_availability_guard: bool = True
    allow_dry_run_completion: bool = True
    block_real_click_when_live_capture_no_click: bool = True
    live_data_capture_no_click_mode: bool = True
    action_real_click_enabled: bool = False
    action_dry_run: bool = True
    required_plan_source: str = "Action_Runtime_Plan_JSON"


@dataclass(frozen=True)
class ClickExecutionRequest:
    """Minimal data needed before a dry-run/real click can be confirmed."""

    table_id: str
    hand_id: str
    street: str
    decision_id: str
    action: str
    target_button_class: str
    click_point: Point
    slot_bbox: BBox
    action_runtime_plan: Mapping[str, Any]
    already_executed_decision_ids: Iterable[str] = field(default_factory=tuple)
    dry_run: bool = True
    real_click_enabled: bool = False


def _as_float_tuple_4(value: Sequence[Any]) -> Optional[BBox]:
    if len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _as_float_tuple_2(value: Sequence[Any]) -> Optional[Point]:
    if len(value) != 2:
        return None
    try:
        x, y = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    return x, y


def point_inside_bbox(point: Sequence[Any], bbox: Sequence[Any], *, inclusive: bool = True) -> bool:
    """Return True if point is inside a slot/table bbox."""
    p = _as_float_tuple_2(point)
    b = _as_float_tuple_4(bbox)
    if p is None or b is None:
        return False
    x, y = p
    x1, y1, x2, y2 = b
    if inclusive:
        return x1 <= x <= x2 and y1 <= y <= y2
    return x1 < x < x2 and y1 < y < y2


def _plan_source_ok(plan: Mapping[str, Any], required_source: str) -> bool:
    source = str(plan.get("source") or plan.get("schema_source") or "")
    schema_version = str(plan.get("schema_version") or "")
    # Runtime plans created by V0.7 may not use source=Action_Runtime_Plan_JSON;
    # they often use source=Action_Decision_JSON while being stored as a runtime plan.
    # Therefore we also accept the runtime-plan schema marker.
    return source == required_source or schema_version.startswith("action_runtime_plan")


def _target_button_available(plan: Mapping[str, Any], target_button_class: str) -> bool:
    if not target_button_class:
        return False

    candidates: List[str] = []
    for key in ("target_sequence", "target_button_classes"):
        value = plan.get(key)
        if isinstance(value, list):
            candidates.extend(str(v) for v in value)

    sequences = plan.get("target_sequences")
    if isinstance(sequences, list):
        for seq in sequences:
            if isinstance(seq, list):
                candidates.extend(str(v) for v in seq)

    return str(target_button_class) in set(candidates)


def build_blocked_result(
    *,
    request: ClickExecutionRequest,
    reason: str,
    message: str,
    config: ClickGuardConfig,
    guard_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": "click_result_v09",
        "status": "blocked",
        "reason": reason,
        "message": message,
        "table_id": request.table_id,
        "hand_id": request.hand_id,
        "street": request.street,
        "decision_id": request.decision_id,
        "action": request.action,
        "target_button_class": request.target_button_class,
        "dry_run": bool(request.dry_run),
        "real_click_enabled": bool(request.real_click_enabled),
        "real_click_master_armed": bool(config.real_click_master_armed),
        "guard_passed": False,
        "guards": guard_details or {},
    }


def validate_click_execution_request(
    request: ClickExecutionRequest,
    config: Optional[ClickGuardConfig] = None,
) -> Dict[str, Any]:
    """Validate all pre-click guards and return a compact click_result payload."""
    cfg = config or ClickGuardConfig()
    guards: Dict[str, Any] = {
        "guard_enabled": bool(cfg.enabled),
        "slot_boundary_guard": None,
        "no_repeat_decision_guard": None,
        "button_availability_guard": None,
        "real_click_master_guard": None,
        "live_no_click_guard": None,
        "dry_run_guard": None,
        "plan_source_guard": None,
    }

    if not cfg.enabled:
        return {
            "schema_version": "click_result_v09",
            "status": "allowed",
            "reason": "guard_disabled",
            "message": "Click execution guard is disabled by config.",
            "table_id": request.table_id,
            "hand_id": request.hand_id,
            "street": request.street,
            "decision_id": request.decision_id,
            "action": request.action,
            "target_button_class": request.target_button_class,
            "dry_run": bool(request.dry_run),
            "real_click_enabled": bool(request.real_click_enabled),
            "guard_passed": True,
            "guards": guards,
        }

    action = str(request.action or "").strip().lower()
    if action not in _ALLOWED_ACTIONS:
        return build_blocked_result(
            request=request,
            reason="invalid_action",
            message=f"Unsupported action for click execution: {request.action!r}",
            config=cfg,
            guard_details=guards,
        )

    plan_source_ok = _plan_source_ok(request.action_runtime_plan, cfg.required_plan_source)
    guards["plan_source_guard"] = plan_source_ok
    if not plan_source_ok:
        return build_blocked_result(
            request=request,
            reason="invalid_runtime_plan_source",
            message="Action runtime plan source/schema does not match the required runtime-plan contract.",
            config=cfg,
            guard_details=guards,
        )

    if cfg.require_button_availability_guard:
        available = _target_button_available(request.action_runtime_plan, request.target_button_class)
        guards["button_availability_guard"] = available
        if not available:
            return build_blocked_result(
                request=request,
                reason="target_button_not_in_runtime_plan",
                message=f"Target button {request.target_button_class!r} is not allowed by Action_Runtime_Plan_JSON.",
                config=cfg,
                guard_details=guards,
            )

    if cfg.require_slot_boundary_guard:
        inside = point_inside_bbox(request.click_point, request.slot_bbox)
        guards["slot_boundary_guard"] = inside
        if not inside:
            return build_blocked_result(
                request=request,
                reason="click_point_outside_slot_bbox",
                message="Click point is outside the table slot bbox; physical/dry-run click is blocked.",
                config=cfg,
                guard_details=guards,
            )

    if cfg.require_no_repeat_decision_guard:
        already = set(str(x) for x in request.already_executed_decision_ids)
        not_repeated = str(request.decision_id) not in already
        guards["no_repeat_decision_guard"] = not_repeated
        if not not_repeated:
            return build_blocked_result(
                request=request,
                reason="decision_id_already_executed",
                message="This decision_id has already been executed in the current runtime scope.",
                config=cfg,
                guard_details=guards,
            )

    wants_real_click = bool(request.real_click_enabled) and not bool(request.dry_run)
    guards["real_click_master_guard"] = (not wants_real_click) or bool(cfg.real_click_master_armed)
    if wants_real_click and not cfg.real_click_master_armed:
        return build_blocked_result(
            request=request,
            reason="real_click_master_not_armed",
            message="Real click requested, but V09_REAL_CLICK_MASTER_ARMED is False.",
            config=cfg,
            guard_details=guards,
        )

    guards["live_no_click_guard"] = not (
        wants_real_click and cfg.block_real_click_when_live_capture_no_click and cfg.live_data_capture_no_click_mode
    )
    if not guards["live_no_click_guard"]:
        return build_blocked_result(
            request=request,
            reason="live_data_capture_no_click_mode",
            message="Real click is blocked because live data capture no-click mode is enabled.",
            config=cfg,
            guard_details=guards,
        )

    guards["dry_run_guard"] = bool(request.dry_run) and cfg.allow_dry_run_completion or wants_real_click
    if bool(request.dry_run) and not cfg.allow_dry_run_completion:
        return build_blocked_result(
            request=request,
            reason="dry_run_completion_not_allowed",
            message="Dry-run click completion is disabled by config.",
            config=cfg,
            guard_details=guards,
        )

    return {
        "schema_version": "click_result_v09",
        "status": "dry_run" if request.dry_run else "ready_for_real_click",
        "reason": "all_click_execution_guards_passed",
        "message": "Click execution guards passed; dry-run is confirmed." if request.dry_run else "Click execution guards passed; real click may be executed by mouse runtime.",
        "table_id": request.table_id,
        "hand_id": request.hand_id,
        "street": request.street,
        "decision_id": request.decision_id,
        "action": action,
        "target_button_class": request.target_button_class,
        "click_point": {"x": float(request.click_point[0]), "y": float(request.click_point[1])},
        "slot_bbox": {
            "x1": float(request.slot_bbox[0]),
            "y1": float(request.slot_bbox[1]),
            "x2": float(request.slot_bbox[2]),
            "y2": float(request.slot_bbox[3]),
        },
        "dry_run": bool(request.dry_run),
        "real_click_enabled": bool(request.real_click_enabled),
        "real_click_master_armed": bool(cfg.real_click_master_armed),
        "guard_passed": True,
        "guards": guards,
    }
