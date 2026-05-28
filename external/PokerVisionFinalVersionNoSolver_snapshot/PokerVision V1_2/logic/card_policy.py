r"""
logic/card_policy.py

PokerVision Core V0.6 — deterministic policy for Card_Detector output.
"""

from __future__ import annotations

from collections import Counter
from typing import List, Optional, Tuple

from config import CARD_CLASSES, CARD_DETECT_THRESHOLD
from detectors.card_detector import CardDetection


CARD_CLASS_SET = set(CARD_CLASSES)
BOARD_STREET_BY_CARD_COUNT = {3: "flop", 4: "turn", 5: "river"}


def _detected(detection: CardDetection) -> bool:
    return detection.confidence >= CARD_DETECT_THRESHOLD


def _x_center(detection: CardDetection) -> float:
    x1, _, x2, _ = detection.bbox_xyxy
    return (float(x1) + float(x2)) / 2.0


def _clean_card_detections(raw_detections: List[CardDetection]) -> Tuple[List[CardDetection], List[str]]:
    warnings: List[str] = []
    filtered = [detection for detection in raw_detections if _detected(detection)]

    unknown = sorted({
        str(detection.class_name)
        for detection in filtered
        if str(detection.class_name) not in CARD_CLASS_SET
    })
    if unknown:
        warnings.append(f"unknown Card_Detector classes ignored: {unknown}")

    clean = [detection for detection in filtered if str(detection.class_name) in CARD_CLASS_SET]
    clean.sort(key=_x_center)
    return clean, warnings


def parse_board_cards(
    raw_detections: List[CardDetection],
) -> Tuple[List[str], Optional[str], List[str]]:
    """
    Valid board outputs:
    - 3 unique cards -> flop
    - 4 unique cards -> turn
    - 5 unique cards -> river
    """
    clean, warnings = _clean_card_detections(raw_detections)
    names = [str(detection.class_name) for detection in clean]

    duplicates = sorted(class_name for class_name, count in Counter(names).items() if count > 1)
    if duplicates:
        warnings.append(f"duplicate board card classes rejected: {duplicates}")
        return [], None, warnings

    if len(names) not in BOARD_STREET_BY_CARD_COUNT:
        warnings.append(
            f"invalid board card count: expected 3, 4 or 5 unique cards, got {len(names)}."
        )
        return [], None, warnings

    return names, BOARD_STREET_BY_CARD_COUNT[len(names)], warnings


def parse_hero_cards(raw_detections: List[CardDetection]) -> Tuple[List[str], List[str]]:
    """Valid HERO output must contain exactly 2 unique card classes."""
    clean, warnings = _clean_card_detections(raw_detections)
    names = [str(detection.class_name) for detection in clean]

    duplicates = sorted(class_name for class_name, count in Counter(names).items() if count > 1)
    if duplicates:
        warnings.append(f"duplicate HERO card classes rejected: {duplicates}")
        return [], warnings

    if len(names) != 2:
        warnings.append(f"invalid HERO card count: expected 2 unique cards, got {len(names)}.")
        return [], warnings

    return names, warnings
