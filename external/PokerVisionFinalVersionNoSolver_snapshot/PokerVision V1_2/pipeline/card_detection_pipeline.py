r"""
pipeline/card_detection_pipeline.py

PokerVision Core V0.6 — Card_Detector normalization pipeline.

Clean JSON enrichment only:
- table_structure.classes.Board.cards
- table_structure.classes.Board.street
- players.seats.Player_seat1.hero_cards
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    CARD_DETECTION_ENABLED,
    CARD_HERO_SEAT_NAME,
    SAVE_DEBUG_CARD_CROPS,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARNING,
    ensure_dir,
)
from detectors.card_detector import run_card_detector
from logic.card_policy import parse_board_cards, parse_hero_cards


@dataclass
class CardDetectionPipelineResult:
    table_structure_block: Dict[str, Any]
    players_block: Dict[str, Any]
    status: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _clamp_bbox_xyxy(bbox_xyxy: List[int], image_size: Any) -> List[int]:
    width, height = image_size
    x1, y1, x2, y2 = bbox_xyxy
    x1 = max(0, min(int(x1), int(width)))
    x2 = max(0, min(int(x2), int(width)))
    y1 = max(0, min(int(y1), int(height)))
    y2 = max(0, min(int(y2), int(height)))
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid card crop bbox after clamp: {[x1, y1, x2, y2]}")
    return [x1, y1, x2, y2]


def _crop_card_roi(table_roi_image: Any, bbox_xyxy: List[int]) -> Any:
    x1, y1, x2, y2 = _clamp_bbox_xyxy(bbox_xyxy, table_roi_image.size)
    return table_roi_image.crop((x1, y1, x2, y2))


def _save_card_crop(*, cycle_dir: Path, hand_id: str, table_id: str, card_key: str, card_roi_image: Any) -> None:
    if not SAVE_DEBUG_CARD_CROPS:
        return
    crop_dir = cycle_dir / "_debug" / hand_id / "card_crops" / table_id
    ensure_dir(crop_dir)
    card_roi_image.save(crop_dir / f"{card_key}.png")


def build_skipped_card_detection_result(
    *,
    table_structure_block: Dict[str, Any],
    players_block: Dict[str, Any],
    reason: str,
) -> CardDetectionPipelineResult:
    table_copy = copy.deepcopy(table_structure_block)
    players_copy = copy.deepcopy(players_block)
    players_copy["next_stage_hint"] = None
    return CardDetectionPipelineResult(
        table_structure_block=table_copy,
        players_block=players_copy,
        status=STATUS_SKIPPED,
        warnings=[],
        errors=[],
    )


def run_card_detection_pipeline(
    *,
    table_roi_image: Any,
    table_id: str,
    hand_id: str,
    cycle_dir: Path,
    table_structure_block: Dict[str, Any],
    players_block: Dict[str, Any],
    board_region: Optional[List[int]],
    player_seat_regions: Dict[str, List[int]],
) -> CardDetectionPipelineResult:
    if not CARD_DETECTION_ENABLED:
        return build_skipped_card_detection_result(
            table_structure_block=table_structure_block,
            players_block=players_block,
            reason="CARD_DETECTION_ENABLED=False",
        )

    table_copy = copy.deepcopy(table_structure_block)
    players_copy = copy.deepcopy(players_block)
    warnings: List[str] = []
    errors: List[str] = []

    board_block = table_copy.get("classes", {}).get("Board")
    if board_block is not None:
        board_block.setdefault("cards", [])
        board_block.setdefault("street", "preflop" if not board_block.get("detect") else None)
        if board_block.get("detect"):
            if board_region is None:
                warnings.append(f"{table_id}: Board detected but runtime Board region is missing.")
                board_block["cards"] = []
                board_block["street"] = None
            else:
                try:
                    board_roi = _crop_card_roi(table_roi_image, board_region)
                    _save_card_crop(
                        cycle_dir=cycle_dir,
                        hand_id=hand_id,
                        table_id=table_id,
                        card_key="Board",
                        card_roi_image=board_roi,
                    )
                    raw_detections = run_card_detector(board_roi)
                    cards, street, parser_warnings = parse_board_cards(raw_detections)
                    board_block["cards"] = cards
                    board_block["street"] = street
                    warnings.extend(f"{table_id}/Board: {item}" for item in parser_warnings)
                except Exception as exc:
                    errors.append(f"Card_Detector failed for {table_id}/Board: {exc}")
                    board_block["cards"] = []
                    board_block["street"] = None
        else:
            board_block["cards"] = []
            board_block["street"] = "preflop"

    seat_blocks = players_copy.get("seats", {})
    hero_block = seat_blocks.get(CARD_HERO_SEAT_NAME)
    if hero_block is None:
        warnings.append(f"{table_id}: HERO seat {CARD_HERO_SEAT_NAME} is missing from players block.")
    else:
        hero_block.setdefault("hero_cards", [])
        hero_region = player_seat_regions.get(CARD_HERO_SEAT_NAME)
        if hero_region is None:
            warnings.append(f"{table_id}: HERO seat {CARD_HERO_SEAT_NAME} runtime region is missing.")
            hero_block["hero_cards"] = []
        else:
            try:
                hero_roi = _crop_card_roi(table_roi_image, hero_region)
                _save_card_crop(
                    cycle_dir=cycle_dir,
                    hand_id=hand_id,
                    table_id=table_id,
                    card_key=f"{CARD_HERO_SEAT_NAME}_HERO",
                    card_roi_image=hero_roi,
                )
                raw_detections = run_card_detector(hero_roi)
                hero_cards, parser_warnings = parse_hero_cards(raw_detections)
                hero_block["hero_cards"] = hero_cards
                warnings.extend(f"{table_id}/{CARD_HERO_SEAT_NAME}/HERO: {item}" for item in parser_warnings)
            except Exception as exc:
                errors.append(f"Card_Detector failed for {table_id}/{CARD_HERO_SEAT_NAME}: {exc}")
                hero_block["hero_cards"] = []

    status = STATUS_OK
    if warnings:
        status = STATUS_WARNING
    if errors:
        status = STATUS_ERROR
    players_copy["next_stage_hint"] = None

    return CardDetectionPipelineResult(
        table_structure_block=table_copy,
        players_block=players_copy,
        status=status,
        warnings=warnings,
        errors=errors,
    )
