r"""
pipeline/table_structure_pipeline.py

PokerVision Core V0.6 — Table structure normalization pipeline.

Stage boundary:
- input: ROI of one table_N;
- model: Table_Seat_BoardPot_Detector;
- output clean JSON block: table_structure with only table-level objects;
- runtime output: detected_player_seats + player_seat_regions for the players stage;
- does not run Card_Detector, Digit_Detector, solver, or clicks.

V0.6 clean JSON rule:
- Player_seat1..Player_seat6 are no longer duplicated inside table_structure;
- player seats are exported only once later, in the compact players block;
- table_structure keeps only table-level classes: Board and Total_pot.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARNING,
    TABLE_STRUCTURE_DETECT_THRESHOLD,
    TABLE_STRUCTURE_ENABLED,
)
from detectors.table_seat_boardpot_detector import (
    TableStructureDetection,
    run_table_structure_detector,
)
from logic.table_format_policy import (
    PLAYER_SEAT_CLASS_ORDER,
    TABLE_STRUCTURE_CLASS_ORDER,
    build_player_seat_processing_queue,
    determine_table_format,
    is_known_table_structure_class,
)


CLEAN_TABLE_STRUCTURE_CLASS_ORDER: List[str] = [
    "Board",
    "Total_pot",
]

TABLE_STRUCTURE_CLASS_ALIASES: Dict[str, str] = {
    "player_seat1": "Player_seat1",
    "player_seat2": "Player_seat2",
    "player_seat3": "Player_seat3",
    "player_seat4": "Player_seat4",
    "player_seat5": "Player_seat5",
    "player_seat6": "Player_seat6",
    "Player_seat_1": "Player_seat1",
    "Player_seat_2": "Player_seat2",
    "Player_seat_3": "Player_seat3",
    "Player_seat_4": "Player_seat4",
    "Player_seat_5": "Player_seat5",
    "Player_seat_6": "Player_seat6",
    "player_seat_1": "Player_seat1",
    "player_seat_2": "Player_seat2",
    "player_seat_3": "Player_seat3",
    "player_seat_4": "Player_seat4",
    "player_seat_5": "Player_seat5",
    "player_seat_6": "Player_seat6",
    "board": "Board",
    "total_pot": "Total_pot",
    "TotalPot": "Total_pot",
    "TotalPot_chips": "Total_pot",
    "totalpot": "Total_pot",
}


@dataclass
class TableStructurePipelineResult:
    table_structure_block: Dict[str, Any]
    # Runtime-only data. Not written to clean JSON.
    detected_player_seats: List[str] = field(default_factory=list)
    player_seat_regions: Dict[str, List[int]] = field(default_factory=dict)
    total_pot_region: Optional[List[int]] = None
    board_region: Optional[List[int]] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _canonical_class_name(class_name: str) -> str:
    normalized = str(class_name).strip()
    return TABLE_STRUCTURE_CLASS_ALIASES.get(normalized, normalized)


def _empty_class_block(class_name: str) -> Dict[str, Any]:
    block = {
        "class_name": class_name,
        "detect": False,
    }

    # V0.6 keeps downstream stage outputs in the source semantic block.
    if class_name == "Total_pot":
        block["value"] = None
    elif class_name == "Board":
        block["cards"] = []
        block["street"] = "preflop"

    return block


def _detected(confidence: float) -> bool:
    return confidence >= TABLE_STRUCTURE_DETECT_THRESHOLD


def _bbox_to_int_xyxy(bbox_xyxy: List[float]) -> List[int]:
    if len(bbox_xyxy) != 4:
        raise ValueError(f"Expected bbox with 4 coordinates, got: {bbox_xyxy}")
    x1, y1, x2, y2 = bbox_xyxy
    return [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))]


def _best_detection_by_class(raw_detections: List[TableStructureDetection]) -> Dict[str, TableStructureDetection]:
    best: Dict[str, TableStructureDetection] = {}

    for detection in raw_detections:
        canonical_name = _canonical_class_name(detection.class_name)
        if not is_known_table_structure_class(canonical_name):
            continue

        current = best.get(canonical_name)
        if current is None or detection.confidence > current.confidence:
            best[canonical_name] = detection

    return best


def _unknown_raw_class_names(raw_detections: List[TableStructureDetection]) -> List[str]:
    unknown = set()
    for detection in raw_detections:
        canonical_name = _canonical_class_name(detection.class_name)
        if not is_known_table_structure_class(canonical_name):
            unknown.add(str(detection.class_name))
    return sorted(unknown)


def build_skipped_table_structure_block(reason: str) -> TableStructurePipelineResult:
    classes = {class_name: _empty_class_block(class_name) for class_name in CLEAN_TABLE_STRUCTURE_CLASS_ORDER}
    block = {
        "status": STATUS_SKIPPED,
        "processing_time_ms": 0,
        "model_name": "Table_Seat_BoardPot_Detector",
        "input_scope": "table_roi",
        "thresholds": {"detect": TABLE_STRUCTURE_DETECT_THRESHOLD},
        "classes": classes,
        "detected_classes": [],
        "seat_count": 0,
        "table_format": None,
        "next_stage_hint": None,
        "reason": reason,
    }
    return TableStructurePipelineResult(
        table_structure_block=block,
        detected_player_seats=[],
        player_seat_regions={},
        total_pot_region=None,
        warnings=[],
    )


def run_table_structure_pipeline(table_roi_image: Any, table_id: str) -> TableStructurePipelineResult:
    if not TABLE_STRUCTURE_ENABLED:
        return build_skipped_table_structure_block("TABLE_STRUCTURE_ENABLED=False")

    started_at = time.perf_counter()
    warnings: List[str] = []
    errors: List[str] = []
    classes = {class_name: _empty_class_block(class_name) for class_name in CLEAN_TABLE_STRUCTURE_CLASS_ORDER}

    try:
        raw_detections = run_table_structure_detector(table_roi_image)
    except Exception as exc:
        error_message = f"Table_Seat_BoardPot_Detector failed for {table_id}: {exc}"
        errors.append(error_message)
        block = {
            "status": STATUS_ERROR,
            "processing_time_ms": _elapsed_ms(started_at),
            "model_name": "Table_Seat_BoardPot_Detector",
            "input_scope": "table_roi",
            "thresholds": {"detect": TABLE_STRUCTURE_DETECT_THRESHOLD},
            "classes": classes,
            "detected_classes": [],
            "seat_count": 0,
            "table_format": None,
            "raw_detection_count": 0,
            "next_stage_hint": None,
            "error": error_message,
        }
        return TableStructurePipelineResult(
            table_structure_block=block,
            detected_player_seats=[],
            player_seat_regions={},
            total_pot_region=None,
            board_region=None,
            warnings=warnings,
            errors=errors,
        )

    unknown_classes = _unknown_raw_class_names(raw_detections)
    if unknown_classes:
        warnings.append(f"{table_id}: unknown Table_Seat_BoardPot classes ignored in clean JSON: {unknown_classes}")

    best_by_class = _best_detection_by_class(raw_detections)

    detected_table_classes: List[str] = []
    detected_player_seats: List[str] = []
    player_seat_regions: Dict[str, List[int]] = {}
    total_pot_region: Optional[List[int]] = None
    board_region: Optional[List[int]] = None

    # Runtime extraction keeps all model classes.
    for class_name in TABLE_STRUCTURE_CLASS_ORDER:
        detection = best_by_class.get(class_name)
        if detection is None or not _detected(detection.confidence):
            continue

        if class_name in PLAYER_SEAT_CLASS_ORDER:
            detected_player_seats.append(class_name)
            try:
                player_seat_regions[class_name] = _bbox_to_int_xyxy(detection.bbox_xyxy)
            except Exception as exc:
                warnings.append(f"{table_id}: invalid bbox for {class_name}: {exc}")
        elif class_name == "Total_pot":
            try:
                total_pot_region = _bbox_to_int_xyxy(detection.bbox_xyxy)
            except Exception as exc:
                warnings.append(f"{table_id}: invalid bbox for Total_pot: {exc}")
        elif class_name == "Board":
            try:
                board_region = _bbox_to_int_xyxy(detection.bbox_xyxy)
            except Exception as exc:
                warnings.append(f"{table_id}: invalid bbox for Board: {exc}")

    # Clean JSON table_structure keeps only table-level objects.
    for class_name in CLEAN_TABLE_STRUCTURE_CLASS_ORDER:
        detection = best_by_class.get(class_name)
        if detection is None:
            continue

        block = _empty_class_block(class_name)
        if _detected(detection.confidence):
            block["detect"] = True
            detected_table_classes.append(class_name)

        classes[class_name] = block

    format_result = determine_table_format(detected_player_seats)
    if format_result.get("warning"):
        warnings.append(f"{table_id}: {format_result['warning']}")

    processing_queue = build_player_seat_processing_queue(detected_player_seats)

    status = STATUS_OK
    if warnings or format_result["status"] == STATUS_WARNING:
        status = STATUS_WARNING
    if errors:
        status = STATUS_ERROR

    next_stage_hint: Optional[str]
    if processing_queue:
        next_stage_hint = "players_pipeline_ready"
    elif "Board" in detected_table_classes or "Total_pot" in detected_table_classes:
        next_stage_hint = "partial_structure_regions_ready"
    else:
        next_stage_hint = None

    block = {
        "status": status,
        "processing_time_ms": _elapsed_ms(started_at),
        "model_name": "Table_Seat_BoardPot_Detector",
        "input_scope": "table_roi",
        "thresholds": {"detect": TABLE_STRUCTURE_DETECT_THRESHOLD},
        "classes": classes,
        "detected_classes": detected_table_classes,
        "seat_count": int(format_result["seat_count"]),
        "table_format": format_result["table_format"],
        "raw_detection_count": len(raw_detections),
        "next_stage_hint": next_stage_hint,
    }

    return TableStructurePipelineResult(
        table_structure_block=block,
        detected_player_seats=build_player_seat_processing_queue(detected_player_seats),
        player_seat_regions=player_seat_regions,
        total_pot_region=total_pot_region,
        board_region=board_region,
        warnings=warnings,
        errors=errors,
    )
