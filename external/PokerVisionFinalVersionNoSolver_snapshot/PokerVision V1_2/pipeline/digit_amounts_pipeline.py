r"""
pipeline/digit_amounts_pipeline.py

PokerVision Core V0.6 — Digit_Detector amounts pipeline.

Stage boundary:
- input: table ROI + runtime amount regions from previous stages;
- model: Digit_Detector;
- clean JSON output: enrich existing semantic places instead of creating a new block:
    table_structure.classes.Total_pot.value
    players.seats.Player_seatN.stack.value
    players.seats.Player_seatN.stack.all_in
    players.seats.Player_seatN.chips.value
- does not run card detectors, solver, or clicks.

V0.6 rule:
- Total_pot value belongs to table_structure;
- Stack and Chips values belong to their Player_seatN in players;
- All-in can be written only from Stack ROI.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    DIGIT_AMOUNTS_ENABLED,
    DIGIT_DETECT_THRESHOLD,
    SAVE_DEBUG_AMOUNT_CROPS,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARNING,
    ensure_dir,
)
from detectors.digit_detector import run_digit_detector
from logic.digit_amount_parser import parse_digit_amount_detections
from logic.positions_builder import apply_preflop_blind_anchor_participation_check


@dataclass
class DigitAmountsPipelineResult:
    table_structure_block: Dict[str, Any]
    players_block: Dict[str, Any]
    status: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _clamp_bbox_xyxy(bbox_xyxy: List[int], image_size: Any) -> List[int]:
    width, height = image_size
    x1, y1, x2, y2 = bbox_xyxy

    x1 = max(0, min(int(x1), int(width)))
    x2 = max(0, min(int(x2), int(width)))
    y1 = max(0, min(int(y1), int(height)))
    y2 = max(0, min(int(y2), int(height)))

    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid amount crop bbox after clamp: {[x1, y1, x2, y2]}")

    return [x1, y1, x2, y2]


def _crop_amount_roi(table_roi_image: Any, bbox_xyxy: List[int]) -> Any:
    x1, y1, x2, y2 = _clamp_bbox_xyxy(bbox_xyxy, table_roi_image.size)
    return table_roi_image.crop((x1, y1, x2, y2))


def _save_amount_crop(
    *,
    cycle_dir: Path,
    hand_id: str,
    table_id: str,
    amount_key: str,
    amount_roi_image: Any,
) -> None:
    if not SAVE_DEBUG_AMOUNT_CROPS:
        return

    crop_dir = cycle_dir / "_debug" / hand_id / "amount_crops" / table_id
    ensure_dir(crop_dir)
    amount_roi_image.save(crop_dir / f"{amount_key}.png")


def build_skipped_digit_amounts_result(
    *,
    table_structure_block: Dict[str, Any],
    players_block: Dict[str, Any],
    reason: str,
) -> DigitAmountsPipelineResult:
    table_copy = copy.deepcopy(table_structure_block)
    players_copy = copy.deepcopy(players_block)
    players_copy["next_stage_hint"] = "card_detection_pipeline_ready"
    return DigitAmountsPipelineResult(
        table_structure_block=table_copy,
        players_block=players_copy,
        status=STATUS_SKIPPED,
        warnings=[],
        errors=[],
    )


def run_digit_amounts_pipeline(
    *,
    table_roi_image: Any,
    table_id: str,
    hand_id: str,
    cycle_dir: Path,
    table_structure_block: Dict[str, Any],
    players_block: Dict[str, Any],
    total_pot_region: Optional[List[int]],
    player_amount_regions: Dict[str, Dict[str, List[int]]],
) -> DigitAmountsPipelineResult:
    if not DIGIT_AMOUNTS_ENABLED:
        return build_skipped_digit_amounts_result(
            table_structure_block=table_structure_block,
            players_block=players_block,
            reason="DIGIT_AMOUNTS_ENABLED=False",
        )

    started_at = time.perf_counter()
    table_copy = copy.deepcopy(table_structure_block)
    players_copy = copy.deepcopy(players_block)
    warnings: List[str] = []
    errors: List[str] = []
    processed_amounts = 0

    total_pot_block = table_copy.get("classes", {}).get("Total_pot")
    if total_pot_block and total_pot_block.get("detect"):
        if total_pot_region is None:
            warnings.append(f"{table_id}: Total_pot detected but runtime amount region is missing.")
        else:
            try:
                amount_roi = _crop_amount_roi(table_roi_image, total_pot_region)
                _save_amount_crop(
                    cycle_dir=cycle_dir,
                    hand_id=hand_id,
                    table_id=table_id,
                    amount_key="Total_pot",
                    amount_roi_image=amount_roi,
                )
                raw_detections = run_digit_detector(amount_roi)
                value, _all_in, parser_warnings = parse_digit_amount_detections(
                    raw_detections,
                    amount_scope="total_pot",
                )
                total_pot_block["value"] = value
                processed_amounts += 1
                warnings.extend(f"{table_id}/Total_pot: {item}" for item in parser_warnings)
            except Exception as exc:
                errors.append(f"Digit_Detector failed for {table_id}/Total_pot: {exc}")

    seat_blocks = players_copy.get("seats", {})
    for seat_name, seat_block in seat_blocks.items():
        seat_regions = player_amount_regions.get(seat_name, {})

        stack_block = seat_block.get("stack")
        if stack_block and stack_block.get("detect"):
            stack_region = seat_regions.get("Stack")
            if stack_region is None:
                warnings.append(f"{table_id}/{seat_name}: Stack detected but runtime amount region is missing.")
            else:
                try:
                    amount_roi = _crop_amount_roi(table_roi_image, stack_region)
                    _save_amount_crop(
                        cycle_dir=cycle_dir,
                        hand_id=hand_id,
                        table_id=table_id,
                        amount_key=f"{seat_name}_Stack",
                        amount_roi_image=amount_roi,
                    )
                    raw_detections = run_digit_detector(amount_roi)
                    value, all_in, parser_warnings = parse_digit_amount_detections(
                        raw_detections,
                        amount_scope="stack",
                    )
                    stack_block["value"] = value
                    stack_block["all_in"] = all_in
                    processed_amounts += 1
                    warnings.extend(f"{table_id}/{seat_name}/Stack: {item}" for item in parser_warnings)
                except Exception as exc:
                    errors.append(f"Digit_Detector failed for {table_id}/{seat_name}/Stack: {exc}")

        chips_block = seat_block.get("chips")
        if chips_block and chips_block.get("detect"):
            chips_region = seat_regions.get("Chips")
            if chips_region is None:
                warnings.append(f"{table_id}/{seat_name}: Chips detected but runtime amount region is missing.")
            else:
                try:
                    amount_roi = _crop_amount_roi(table_roi_image, chips_region)
                    _save_amount_crop(
                        cycle_dir=cycle_dir,
                        hand_id=hand_id,
                        table_id=table_id,
                        amount_key=f"{seat_name}_Chips",
                        amount_roi_image=amount_roi,
                    )
                    raw_detections = run_digit_detector(amount_roi)
                    value, _all_in, parser_warnings = parse_digit_amount_detections(
                        raw_detections,
                        amount_scope="chips",
                    )
                    chips_block["value"] = value
                    processed_amounts += 1
                    warnings.extend(f"{table_id}/{seat_name}/Chips: {item}" for item in parser_warnings)
                except Exception as exc:
                    errors.append(f"Digit_Detector failed for {table_id}/{seat_name}/Chips: {exc}")

    # V0.6 preflop hand-participation correction:
    # if Board is absent and folded visual seats are located inside the blind
    # anchor gaps BTN->SB or SB->BB, treat them as logical SitOut for this hand
    # and rebuild the compact position map.
    players_copy = apply_preflop_blind_anchor_participation_check(
        table_structure_block=table_copy,
        players_block=players_copy,
    )

    status = STATUS_OK
    if warnings:
        status = STATUS_WARNING
    if errors:
        status = STATUS_ERROR

    players_copy["next_stage_hint"] = "card_detection_pipeline_ready"

    return DigitAmountsPipelineResult(
        table_structure_block=table_copy,
        players_block=players_copy,
        status=status,
        warnings=warnings,
        errors=errors,
    )
