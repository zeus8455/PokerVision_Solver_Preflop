"""
logic/action_button_slot_roi_guard.py

PokerVision V2.5 — Action_Button_Detector slot ROI guard/audit.

Purpose:
- make the Action_Button_Detector contract explicit: detection input must be one table_N ROI,
  not the full desktop/screen;
- verify that detector-local button bboxes are inside the table ROI;
- verify that a future/dry-run click point is inside the same table slot bbox;
- provide compact audit JSON for tests/runtime diagnostics.

This module does not run YOLO and does not click.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


BBox = Tuple[float, float, float, float]
Point = Tuple[float, float]
Size = Tuple[float, float]

_ALLOWED_SCOPES = {"table_roi", "slot_roi", "table_crop"}
_FORBIDDEN_SCOPES = {"full_screen", "desktop", "monitor", "screen", "all_screens"}


@dataclass(frozen=True)
class ActionButtonSlotRoiGuardRequest:
    table_id: str
    detector_input_scope: str
    slot_bbox: Sequence[Any]
    roi_size: Optional[Sequence[Any]] = None
    local_bbox_xyxy: Optional[Sequence[Any]] = None
    click_point_global: Optional[Sequence[Any]] = None
    source: str = "Action_Button_Detector"


def _as_float_tuple_4(value: Optional[Sequence[Any]]) -> Optional[BBox]:
    if value is None or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _as_float_tuple_2(value: Optional[Sequence[Any]]) -> Optional[Point]:
    if value is None or len(value) != 2:
        return None
    try:
        x, y = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    return x, y


def _as_size(value: Optional[Sequence[Any]]) -> Optional[Size]:
    point = _as_float_tuple_2(value)
    if point is None:
        return None
    w, h = point
    if w <= 0 or h <= 0:
        return None
    return w, h


def _point_inside_bbox(point: Point, bbox: BBox) -> bool:
    x, y = point
    x1, y1, x2, y2 = bbox
    return x1 <= x <= x2 and y1 <= y <= y2


def _local_bbox_inside_roi(local_bbox: BBox, roi_size: Size) -> bool:
    x1, y1, x2, y2 = local_bbox
    w, h = roi_size
    return 0 <= x1 <= x2 <= w and 0 <= y1 <= y2 <= h


def _map_local_bbox_to_global(local_bbox: BBox, slot_bbox: BBox) -> BBox:
    sx1, sy1, _, _ = slot_bbox
    x1, y1, x2, y2 = local_bbox
    return sx1 + x1, sy1 + y1, sx1 + x2, sy1 + y2


def _bbox_inside_bbox(inner: BBox, outer: BBox) -> bool:
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer
    return ox1 <= ix1 <= ix2 <= ox2 and oy1 <= iy1 <= iy2 <= oy2


def validate_action_button_slot_roi_guard(request: ActionButtonSlotRoiGuardRequest) -> Dict[str, Any]:
    """Validate one Action_Button_Detector ROI/click-point contract."""
    errors: List[str] = []
    warnings: List[str] = []
    guards: Dict[str, Optional[bool]] = {
        "detector_input_scope_guard": None,
        "slot_bbox_guard": None,
        "roi_size_guard": None,
        "local_bbox_inside_roi_guard": None,
        "mapped_global_bbox_inside_slot_guard": None,
        "click_point_inside_slot_guard": None,
    }

    table_id = str(request.table_id or "").strip()
    scope = str(request.detector_input_scope or "").strip().lower()

    if not table_id.startswith("table_"):
        errors.append("invalid_table_id")

    if scope in _FORBIDDEN_SCOPES:
        guards["detector_input_scope_guard"] = False
        errors.append("full_screen_action_button_search_forbidden")
    elif scope in _ALLOWED_SCOPES:
        guards["detector_input_scope_guard"] = True
    else:
        guards["detector_input_scope_guard"] = False
        errors.append("unknown_or_missing_detector_input_scope")

    slot_bbox = _as_float_tuple_4(request.slot_bbox)
    guards["slot_bbox_guard"] = slot_bbox is not None
    if slot_bbox is None:
        errors.append("invalid_slot_bbox")

    roi_size = _as_size(request.roi_size)
    if request.roi_size is not None:
        guards["roi_size_guard"] = roi_size is not None
        if roi_size is None:
            errors.append("invalid_roi_size")

    local_bbox = _as_float_tuple_4(request.local_bbox_xyxy)
    if request.local_bbox_xyxy is not None:
        if local_bbox is None:
            errors.append("invalid_local_bbox_xyxy")
            guards["local_bbox_inside_roi_guard"] = False
        elif roi_size is not None:
            local_ok = _local_bbox_inside_roi(local_bbox, roi_size)
            guards["local_bbox_inside_roi_guard"] = local_ok
            if not local_ok:
                errors.append("local_button_bbox_outside_table_roi")
        elif roi_size is None:
            warnings.append("roi_size_missing_local_bbox_boundary_check_skipped")

        if local_bbox is not None and slot_bbox is not None:
            global_bbox = _map_local_bbox_to_global(local_bbox, slot_bbox)
            mapped_ok = _bbox_inside_bbox(global_bbox, slot_bbox)
            guards["mapped_global_bbox_inside_slot_guard"] = mapped_ok
            if not mapped_ok:
                errors.append("mapped_button_bbox_outside_slot_bbox")
        else:
            global_bbox = None
    else:
        global_bbox = None

    click_point = _as_float_tuple_2(request.click_point_global)
    if request.click_point_global is not None:
        if click_point is None:
            guards["click_point_inside_slot_guard"] = False
            errors.append("invalid_click_point_global")
        elif slot_bbox is not None:
            inside = _point_inside_bbox(click_point, slot_bbox)
            guards["click_point_inside_slot_guard"] = inside
            if not inside:
                errors.append("click_point_outside_slot_bbox")
    else:
        warnings.append("click_point_not_provided_detector_roi_audit_only")

    ok = not errors
    return {
        "schema_version": "action_button_slot_roi_guard_v2_5",
        "ok": ok,
        "status": "ACTION_BUTTON_SLOT_ROI_GUARD_OK" if ok else "ACTION_BUTTON_SLOT_ROI_GUARD_BLOCKED",
        "errors": errors,
        "warnings": warnings,
        "table_id": table_id,
        "source": str(request.source or "Action_Button_Detector"),
        "detector_input_scope": scope,
        "slot_bbox": (
            {"x1": slot_bbox[0], "y1": slot_bbox[1], "x2": slot_bbox[2], "y2": slot_bbox[3]}
            if slot_bbox is not None
            else None
        ),
        "roi_size": (
            {"w": roi_size[0], "h": roi_size[1]}
            if roi_size is not None
            else None
        ),
        "local_bbox_xyxy": list(local_bbox) if local_bbox is not None else None,
        "mapped_global_bbox_xyxy": list(global_bbox) if global_bbox is not None else None,
        "click_point_global": (
            {"x": click_point[0], "y": click_point[1]}
            if click_point is not None
            else None
        ),
        "guards": guards,
    }
