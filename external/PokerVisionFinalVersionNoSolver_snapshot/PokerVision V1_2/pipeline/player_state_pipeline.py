r"""
pipeline/player_state_pipeline.py

PokerVision Core V0.6 — compact players normalization pipeline.

Stage boundary:
- input: table ROI + runtime Player_seatN regions from Table_Seat_BoardPot_Detector;
- model: Player_State_Detector;
- runtime helper: positions_builder;
- output clean JSON block: players;
- does not run card/digit detectors, solver, or clicks.

V0.6 clean JSON rule:
- each Player_seatN is written exactly once in players.seats;
- position, Stack, Chips, Fold, SitOut and BTN are merged into that one seat object;
- separate clean JSON blocks player_state and positions are no longer emitted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    PLAYER_STATE_BTN_MISSING_IS_ERROR,
    PLAYER_STATE_CLASSES,
    PLAYER_STATE_DETECT_THRESHOLD,
    PLAYER_STATE_ENABLED,
    SAVE_DEBUG_PLAYER_SEAT_CROPS,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARNING,
    ensure_dir,
)
from detectors.player_state_detector import PlayerStateDetection, run_player_state_detector
from logic.positions_builder import build_positions_block
from logic.table_format_policy import build_player_seat_processing_queue


PLAYER_STATE_CLASS_ORDER: List[str] = list(PLAYER_STATE_CLASSES)

PLAYER_STATE_CLASS_ALIASES: Dict[str, str] = {
    "stack": "Stack",
    "STACK": "Stack",
    "chips": "Chips",
    "chip": "Chips",
    "CHIPS": "Chips",
    "fold": "Fold",
    "Folded": "Fold",
    "folded": "Fold",
    "FOLD": "Fold",
    "sitout": "SitOut",
    "sit_out": "SitOut",
    "Sitout": "SitOut",
    "Sit_Out": "SitOut",
    "sitOut": "SitOut",
    "button": "BTN",
    "Button": "BTN",
    "btn": "BTN",
    "dealer": "BTN",
}


@dataclass
class PlayerStatePipelineResult:
    players_block: Dict[str, Any]
    # Runtime-only table ROI bboxes for next Digit_Detector stage.
    amount_regions: Dict[str, Dict[str, List[int]]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _canonical_class_name(class_name: str) -> str:
    normalized = str(class_name).strip()
    return PLAYER_STATE_CLASS_ALIASES.get(normalized, normalized)


def _is_known_player_state_class(class_name: str) -> bool:
    return class_name in PLAYER_STATE_CLASS_ORDER


def _detected(confidence: float) -> bool:
    return confidence >= PLAYER_STATE_DETECT_THRESHOLD


def _best_detection_by_class(raw_detections: List[PlayerStateDetection]) -> Dict[str, PlayerStateDetection]:
    best: Dict[str, PlayerStateDetection] = {}

    for detection in raw_detections:
        canonical_name = _canonical_class_name(detection.class_name)
        if not _is_known_player_state_class(canonical_name):
            continue

        current = best.get(canonical_name)
        if current is None or detection.confidence > current.confidence:
            best[canonical_name] = detection

    return best


def _unknown_raw_class_names(raw_detections: List[PlayerStateDetection]) -> List[str]:
    unknown = set()
    for detection in raw_detections:
        canonical_name = _canonical_class_name(detection.class_name)
        if not _is_known_player_state_class(canonical_name):
            unknown.add(str(detection.class_name))
    return sorted(unknown)


def _clamp_bbox_xyxy(bbox_xyxy: List[int], image_size: Any) -> List[int]:
    width, height = image_size
    x1, y1, x2, y2 = bbox_xyxy

    x1 = max(0, min(int(x1), int(width)))
    x2 = max(0, min(int(x2), int(width)))
    y1 = max(0, min(int(y1), int(height)))
    y2 = max(0, min(int(y2), int(height)))

    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid Player_seat crop bbox after clamp: {[x1, y1, x2, y2]}")

    return [x1, y1, x2, y2]


def _crop_seat_roi(table_roi_image: Any, bbox_xyxy: List[int]) -> Any:
    x1, y1, x2, y2 = _clamp_bbox_xyxy(bbox_xyxy, table_roi_image.size)
    return table_roi_image.crop((x1, y1, x2, y2))


def _save_player_seat_crop(
    *,
    cycle_dir: Path,
    hand_id: str,
    table_id: str,
    seat_name: str,
    seat_roi_image: Any,
) -> None:
    if not SAVE_DEBUG_PLAYER_SEAT_CROPS:
        return

    crop_dir = cycle_dir / "_debug" / hand_id / "player_seat_crops" / table_id
    ensure_dir(crop_dir)
    seat_roi_image.save(crop_dir / f"{seat_name}.png")


def _empty_compact_seat(
    *,
    status: str,
    position: Optional[str] = None,
    reason: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    seat = {
        "status": status,
        "position": position,
        "stack": {
            "detect": False,
            "value": None,
            "all_in": False,
        },
        "chips": {
            "detect": False,
            "value": None,
        },
        "fold": False,
        "sitout": False,
        "btn": False,
    }

    if reason is not None:
        seat["reason"] = reason
    if error is not None:
        seat["error"] = error

    return seat


def _normalize_seat_state(raw_detections: List[PlayerStateDetection]) -> Dict[str, Any]:
    detected_classes: List[str] = []
    best_by_class = _best_detection_by_class(raw_detections)

    for class_name in PLAYER_STATE_CLASS_ORDER:
        detection = best_by_class.get(class_name)
        if detection is not None and _detected(detection.confidence):
            detected_classes.append(class_name)

    return {
        "stack": "Stack" in detected_classes,
        "chips": "Chips" in detected_classes,
        "fold": "Fold" in detected_classes,
        "sitout": "SitOut" in detected_classes,
        "btn": "BTN" in detected_classes,
        "best_by_class": best_by_class,
    }


def _offset_bbox_to_table_roi(seat_bbox_xyxy: List[int], local_bbox_xyxy: List[float]) -> List[int]:
    seat_x1, seat_y1, _, _ = seat_bbox_xyxy
    local_x1, local_y1, local_x2, local_y2 = local_bbox_xyxy
    return [
        int(round(seat_x1 + local_x1)),
        int(round(seat_y1 + local_y1)),
        int(round(seat_x1 + local_x2)),
        int(round(seat_y1 + local_y2)),
    ]


def build_skipped_player_state_block(reason: str) -> PlayerStatePipelineResult:
    """
    Compatibility function name kept for old imports.
    In V0.6 it returns the compact players block.
    """
    block = {
        "status": STATUS_SKIPPED,
        "processing_time_ms": 0,
        "model_name": "Player_State_Detector",
        "input_scope": "player_seat_roi",
        "thresholds": {"detect": PLAYER_STATE_DETECT_THRESHOLD},
        "btn_seat": None,
        "seats": {},
        "next_stage_hint": None,
        "reason": reason,
    }
    return PlayerStatePipelineResult(players_block=block, amount_regions={}, warnings=[])


def run_player_state_pipeline(
    *,
    table_roi_image: Any,
    table_id: str,
    hand_id: str,
    cycle_dir: Path,
    detected_player_seats: List[str],
    player_seat_regions: Dict[str, List[int]],
) -> PlayerStatePipelineResult:
    if not PLAYER_STATE_ENABLED:
        return build_skipped_player_state_block("PLAYER_STATE_ENABLED=False")

    started_at = time.perf_counter()
    warnings: List[str] = []
    errors: List[str] = []

    processing_queue = build_player_seat_processing_queue(detected_player_seats)
    if not processing_queue:
        return build_skipped_player_state_block("No detected Player_seatN regions for Player_State_Detector.")

    seat_states: Dict[str, Dict[str, Any]] = {}
    amount_regions: Dict[str, Dict[str, List[int]]] = {}
    btn_candidates: List[str] = []
    folded_seats: List[str] = []
    sitout_seats: List[str] = []

    for seat_name in processing_queue:
        bbox = player_seat_regions.get(seat_name)
        if bbox is None:
            warning = f"{table_id}: no runtime bbox for {seat_name}; Player_State_Detector skipped for this seat."
            warnings.append(warning)
            seat_states[seat_name] = _empty_compact_seat(status=STATUS_SKIPPED, reason=warning)
            continue

        try:
            seat_roi = _crop_seat_roi(table_roi_image, bbox)
            _save_player_seat_crop(
                cycle_dir=cycle_dir,
                hand_id=hand_id,
                table_id=table_id,
                seat_name=seat_name,
                seat_roi_image=seat_roi,
            )
            raw_detections = run_player_state_detector(seat_roi)
        except Exception as exc:
            error_message = f"Player_State_Detector failed for {table_id}/{seat_name}: {exc}"
            errors.append(error_message)
            seat_states[seat_name] = _empty_compact_seat(status=STATUS_ERROR, error=error_message)
            continue

        unknown_classes = _unknown_raw_class_names(raw_detections)
        if unknown_classes:
            warnings.append(f"{table_id}/{seat_name}: unknown Player_State classes ignored: {unknown_classes}")

        normalized = _normalize_seat_state(raw_detections)
        best_by_class = normalized["best_by_class"]

        seat_amount_regions: Dict[str, List[int]] = {}
        for amount_class_name in ("Stack", "Chips"):
            amount_detection = best_by_class.get(amount_class_name)
            if amount_detection is None or not _detected(amount_detection.confidence):
                continue
            try:
                seat_amount_regions[amount_class_name] = _offset_bbox_to_table_roi(
                    bbox,
                    amount_detection.bbox_xyxy,
                )
            except Exception as exc:
                warnings.append(
                    f"{table_id}/{seat_name}: invalid runtime bbox for {amount_class_name}: {exc}"
                )

        if seat_amount_regions:
            amount_regions[seat_name] = seat_amount_regions

        if normalized["btn"]:
            btn_candidates.append(seat_name)
        if normalized["fold"]:
            folded_seats.append(seat_name)
        if normalized["sitout"]:
            sitout_seats.append(seat_name)

        seat_states[seat_name] = {
            "status": STATUS_OK,
            "position": None,
            "stack": {
                "detect": normalized["stack"],
                "value": None,
                "all_in": False,
            },
            "chips": {
                "detect": normalized["chips"],
                "value": None,
            },
            "fold": normalized["fold"],
            "sitout": normalized["sitout"],
            "btn": normalized["btn"],
        }

    btn_seat: Optional[str] = None
    if len(btn_candidates) == 1:
        btn_seat = btn_candidates[0]
    elif len(btn_candidates) == 0:
        message = f"{table_id}: BTN was not detected by Player_State_Detector."
        if PLAYER_STATE_BTN_MISSING_IS_ERROR:
            errors.append(message)
        else:
            warnings.append(message)
    else:
        warnings.append(f"{table_id}: multiple BTN candidates detected: {btn_candidates}; first candidate is used.")
        btn_seat = btn_candidates[0]

    positions_result = build_positions_block(
        detected_player_seats=processing_queue,
        btn_seat=btn_seat,
        folded_seats=folded_seats,
        sitout_seats=sitout_seats,
    )

    for warning in positions_result.get("warnings", []):
        warnings.append(f"{table_id}: {warning}")
    for error in positions_result.get("errors", []):
        errors.append(f"{table_id}: {error}")

    seat_positions = positions_result.get("seat_positions", {})
    for seat_name, seat in seat_states.items():
        seat["position"] = seat_positions.get(seat_name)

    status = STATUS_OK
    if warnings or positions_result.get("status") == STATUS_WARNING:
        status = STATUS_WARNING
    if errors:
        status = STATUS_ERROR

    block = {
        "status": status,
        "processing_time_ms": _elapsed_ms(started_at),
        "model_name": "Player_State_Detector",
        "input_scope": "player_seat_roi",
        "thresholds": {"detect": PLAYER_STATE_DETECT_THRESHOLD},
        "btn_seat": btn_seat,
        "seats": seat_states,
        "next_stage_hint": "digit_amounts_pipeline_ready" if positions_result.get("status") == STATUS_OK else None,
    }

    return PlayerStatePipelineResult(
        players_block=block,
        amount_regions=amount_regions,
        warnings=warnings,
        errors=errors,
    )
