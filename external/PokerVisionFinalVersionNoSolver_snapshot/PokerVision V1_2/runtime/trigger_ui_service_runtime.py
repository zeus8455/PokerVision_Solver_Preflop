r"""
runtime/trigger_ui_service_runtime.py

PokerVision Core V1.2 — Trigger_UI service-click protected runtime.

Covered branch:
- Remove_Table / Remove_Game / Exit_cashOut / 1_roll_board / Bunny / True_active_fold;
- Non_active_fold -> HERO cards -> Data_death_card -> dry-run Non_active_fold.

This module is defensive and runtime-only:
- it never writes to clean JSON;
- real clicks are controlled by config and protected by slot guard / anti-repeat / human-like mouse runtime;
- it returns runtime data to the caller; no standalone _runtime JSON report is written.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import (
    CARD_HERO_SEAT_NAME,
    V11_BUNNY_CLICK_PROBABILITY,
    V11_NON_ACTIVE_FOLD_ENABLED,
    V11_TRIGGER_UI_SERVICE_ANTI_REPEAT_SEC,
    V11_TRIGGER_UI_SERVICE_CLICK_ENABLED,
    V11_TRIGGER_UI_SERVICE_DRY_RUN,
    V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED,
    V11_TRIGGER_UI_SERVICE_REQUIRE_BUTTON_DETECTION,
    V11_TRIGGER_UI_SERVICE_SAFE_INNER_BBOX_RATIO,
    V11_TRIGGER_UI_SERVICE_SLOT_GUARD_ENABLED,
)
from detectors.card_detector import run_card_detector
from logic.card_policy import parse_hero_cards
from pipeline.table_structure_pipeline import run_table_structure_pipeline
from runtime.death_card_policy import check_hero_cards_in_death_range
from runtime.trigger_ui_service_policy import (
    describe_service_class,
    detected_only_service_classes,
    first_detected_service_class,
    is_bunny_service_enabled,
    is_simple_service_class,
    is_terminal_service_class,
)
from runtime.table_overlay_status import update_table_runtime_status
from runtime.mouse_human_runtime import execute_click_points_human_like

_SERVICE_EXECUTED_AT: Dict[str, float] = {}


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _now() -> float:
    return time.time()


def _extract_detected_classes(trigger_ui_block: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(trigger_ui_block, dict):
        return []
    detected = trigger_ui_block.get("detected_classes")
    if isinstance(detected, list):
        return [str(item) for item in detected]
    return []


def _extract_hero_cards_from_state(full_state: Dict[str, Any]) -> List[str]:
    players = full_state.get("players") or {}
    seats = players.get("seats") if isinstance(players, dict) else None
    if not isinstance(seats, dict):
        return []
    hero = seats.get(CARD_HERO_SEAT_NAME)
    if not isinstance(hero, dict):
        return []
    cards = hero.get("hero_cards")
    if not isinstance(cards, list):
        return []
    return [str(card) for card in cards if str(card).strip()]


def _clamp_bbox_xyxy(bbox_xyxy: List[int], image_size: Any) -> List[int]:
    width, height = image_size
    x1, y1, x2, y2 = [int(v) for v in bbox_xyxy]
    x1 = max(0, min(x1, int(width)))
    x2 = max(0, min(x2, int(width)))
    y1 = max(0, min(y1, int(height)))
    y2 = max(0, min(y2, int(height)))
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid crop bbox after clamp: {[x1, y1, x2, y2]}")
    return [x1, y1, x2, y2]


def _crop_roi(image: Any, bbox_xyxy: List[int]) -> Any:
    x1, y1, x2, y2 = _clamp_bbox_xyxy(bbox_xyxy, image.size)
    return image.crop((x1, y1, x2, y2))


def _detect_hero_cards_for_non_active_fold(table_roi_image: Any, table_id: str) -> Dict[str, Any]:
    """
    Runtime fallback used only when full_state has no Player_seat1.hero_cards.

    It runs Table_Seat_BoardPot_Detector to get Player_seat1 bbox, then runs
    Card_Detector on that ROI and parses exactly two HERO cards.
    """
    report: Dict[str, Any] = {
        "status": "skipped",
        "source": "runtime_fallback_detector",
        "hero_cards": [],
        "warnings": [],
        "errors": [],
    }

    try:
        structure_result = run_table_structure_pipeline(table_roi_image=table_roi_image, table_id=table_id)
        player_regions = structure_result.player_seat_regions or {}
        hero_region = player_regions.get(CARD_HERO_SEAT_NAME)
        if hero_region is None:
            report["status"] = "error"
            report["errors"].append(f"{CARD_HERO_SEAT_NAME} runtime region was not found for Non_active_fold.")
            return report

        hero_roi = _crop_roi(table_roi_image, hero_region)
        raw_cards = run_card_detector(hero_roi)
        hero_cards, warnings = parse_hero_cards(raw_cards)
        report["warnings"].extend(warnings)
        report["hero_cards"] = hero_cards
        report["status"] = "ok" if len(hero_cards) == 2 else "warning"
        if len(hero_cards) != 2:
            report["errors"].append("Fallback HERO card detection did not return exactly two cards.")
        return report
    except Exception as exc:
        report["status"] = "error"
        report["errors"].append(str(exc))
        return report


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
    return int(slot_bbox.x1) + int(point[0]), int(slot_bbox.y1) + int(point[1])


def _point_inside_slot(global_point: Tuple[int, int], slot_bbox: Any) -> bool:
    x, y = global_point
    return int(slot_bbox.x1) <= x <= int(slot_bbox.x2) and int(slot_bbox.y1) <= y <= int(slot_bbox.y2)


def _build_click_point(target_class: str, best_by_class: Dict[str, Dict[str, Any]], slot: Any) -> List[Dict[str, Any]]:
    detection = best_by_class[target_class]
    bbox = [int(v) for v in detection.get("bbox_xyxy") or []]
    local_point = _bbox_center_inside_safe_zone(bbox, V11_TRIGGER_UI_SERVICE_SAFE_INNER_BBOX_RATIO)
    global_point = _local_point_to_global(local_point, slot.bbox)
    return [
        {
            "class_name": target_class,
            "confidence": detection.get("confidence"),
            "local_bbox_xyxy": bbox,
            "local_click_point": {"x": local_point[0], "y": local_point[1]},
            "global_click_point": {"x": global_point[0], "y": global_point[1]},
            "inside_slot_bbox": _point_inside_slot(global_point, slot.bbox),
        }
    ]


def _make_service_decision_id(table_id: str, hand_id: Any, frame_name: str, target_class: Optional[str]) -> str:
    return f"v11_service_{table_id}_{hand_id or 'unknown_hand'}_{frame_name}_{target_class or 'none'}"


def _finish(report: Dict[str, Any], status: str, message: str, started_at: float) -> Dict[str, Any]:
    report["service_click"]["status"] = status
    report["service_click"]["message"] = message
    report["service_click"]["processing_time_ms"] = _elapsed_ms(started_at)
    return report


def run_v11_trigger_ui_service_runtime(
    *,
    full_state: Dict[str, Any],
    table_roi_image: Any,
    slot: Any,
    trigger_best_by_class: Optional[Dict[str, Dict[str, Any]]],
    cycle_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run Trigger_UI service-click branch in safe dry-run mode."""
    started_at = time.perf_counter()
    table = full_state.get("table") or {}
    trigger_ui = full_state.get("trigger_ui") or {}
    table_id = str(table.get("table_id") or getattr(slot, "table_id", "unknown_table"))
    hand_id = table.get("hand_id")
    frame_name = str(table.get("frame_name") or "unknown_frame")
    detected_classes = _extract_detected_classes(trigger_ui)
    best_by_class = trigger_best_by_class or {}

    report: Dict[str, Any] = {
        "schema_version": "1.1-service-click",
        "table_id": table_id,
        "hand_id": hand_id,
        "frame_name": frame_name,
        "trigger_ui": {
            "detected_classes": detected_classes,
            "runtime_best_classes": sorted(best_by_class.keys()),
            "detected_only_classes": detected_only_service_classes(best_by_class),
        },
        "death_card": {
            "status": "skipped",
            "hero_cards": [],
            "hand_key": None,
            "matched": False,
            "message": None,
        },
        "service_click": {
            "status": "skipped",
            "target_class": None,
            "target_sequence": [],
            "click_points": [],
            "guard_passed": False,
            "dry_run": bool(V11_TRIGGER_UI_SERVICE_DRY_RUN),
            "real_click_enabled": bool(V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED),
            "frame_finished": False,
            "skip_action_button_runtime": False,
            "message": None,
            "processing_time_ms": 0,
        },
    }

    def finalize(status: str, message: str) -> Dict[str, Any]:
        result = _finish(report, status, message, started_at)
        death_card = result.get("death_card", {}) if isinstance(result, dict) else {}
        update_table_runtime_status(
            table_id,
            hand_id=hand_id,
            frame_name=frame_name,
            service_click_status=str(result["service_click"].get("status")),
            service_click_target=result["service_click"].get("target_class"),
            service_click_message=message,
            service_death_card_status=str(death_card.get("status") or "skipped"),
            service_death_card_hand_key=death_card.get("hand_key"),
        )
        return result

    if not V11_TRIGGER_UI_SERVICE_CLICK_ENABLED:
        return finalize("skipped", "Trigger_UI service-click runtime is disabled by config.")

    detected_only = detected_only_service_classes(best_by_class)

    # True_active_fold is a detection-only confirmation that Non_active_fold has
    # already been pressed by the poker client. It must never create a click plan,
    # but it is terminal for the current frame and must skip solver/action buttons.
    if "True_active_fold" in detected_only:
        report["service_click"]["target_class"] = None
        report["service_click"]["target_sequence"] = []
        report["service_click"]["description"] = describe_service_class("True_active_fold")
        report["service_click"]["frame_finished"] = True
        report["service_click"]["skip_action_button_runtime"] = True
        return finalize(
            "confirmed",
            "True_active_fold detected as confirmation of previous Non_active_fold press; no click is planned.",
        )

    target_class = first_detected_service_class(best_by_class)
    if target_class is None:
        if "Remove_Table" in detected_only:
            report["service_click"]["description"] = describe_service_class("Remove_Table")
            return finalize(
                "detected_only",
                "Only Remove_Table was detected; click planning is disabled for Remove_Table.",
            )
        return finalize("skipped", "No actionable Trigger_UI service-click class was detected.")

    report["service_click"]["target_class"] = target_class
    report["service_click"]["target_sequence"] = [target_class]
    report["service_click"]["description"] = describe_service_class(target_class)
    report["service_click"]["frame_finished"] = False

    if V11_TRIGGER_UI_SERVICE_REQUIRE_BUTTON_DETECTION and target_class not in best_by_class:
        return finalize("blocked", f"Runtime bbox for service class {target_class} is missing.")

    # Bunny is intentionally probabilistic.
    if target_class == "Bunny":
        if not is_bunny_service_enabled():
            return finalize("skipped", "Bunny click is disabled by config.")
        roll = random.random()
        report["service_click"]["bunny_probability"] = float(V11_BUNNY_CLICK_PROBABILITY)
        report["service_click"]["bunny_roll"] = roll
        if roll > float(V11_BUNNY_CLICK_PROBABILITY):
            return finalize("skipped", "Bunny detected but probability gate did not pass.")

    # Non_active_fold requires the global death-card range match.
    if target_class == "Non_active_fold":
        if not V11_NON_ACTIVE_FOLD_ENABLED:
            return finalize("skipped", "Non_active_fold runtime is disabled by config.")

        hero_cards = _extract_hero_cards_from_state(full_state)
        hero_source = "full_runtime_json"
        fallback_report = None
        if len(hero_cards) != 2:
            fallback_report = _detect_hero_cards_for_non_active_fold(table_roi_image, table_id)
            hero_cards = list(fallback_report.get("hero_cards") or [])
            hero_source = "runtime_fallback_detector"

        death_report = check_hero_cards_in_death_range(hero_cards)
        death_report["hero_cards_source"] = hero_source
        if fallback_report is not None:
            death_report["fallback_detector"] = fallback_report
        report["death_card"] = death_report

        if not death_report.get("matched"):
            return finalize("skipped", death_report.get("message") or "Hero hand is not in death-card range.")

        report["service_click"]["skip_action_button_runtime"] = True

    elif is_simple_service_class(target_class):
        report["service_click"]["skip_action_button_runtime"] = False

    click_points = _build_click_point(target_class, best_by_class, slot)
    report["service_click"]["click_points"] = click_points

    if V11_TRIGGER_UI_SERVICE_SLOT_GUARD_ENABLED and not all(point["inside_slot_bbox"] for point in click_points):
        return finalize("blocked", "Service click target is outside current slot_bbox.")

    decision_id = _make_service_decision_id(table_id, hand_id, frame_name, target_class)
    report["service_click"]["decision_id"] = decision_id
    previous_at = _SERVICE_EXECUTED_AT.get(decision_id)
    if previous_at is not None and (_now() - previous_at) < V11_TRIGGER_UI_SERVICE_ANTI_REPEAT_SEC:
        return finalize("blocked", "Service decision was already executed recently; anti-repeat blocked click.")

    report["service_click"]["guard_passed"] = True

    if V11_TRIGGER_UI_SERVICE_DRY_RUN or not V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED:
        return finalize("dry_run", f"Dry-run service target selected: {target_class}; physical click disabled.")

    try:
        mouse_report = execute_click_points_human_like(click_points)
        report["service_click"]["mouse"] = mouse_report
        _SERVICE_EXECUTED_AT[decision_id] = _now()
        return finalize("clicked", f"Physical service click executed with human-like mouse runtime: {target_class}.")
    except Exception as exc:
        return finalize("error", f"Service mouse execution failed: {exc}")
