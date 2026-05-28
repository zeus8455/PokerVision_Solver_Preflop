r"""
logic/digit_amount_parser.py

PokerVision Core V0.6 — deterministic parser for Digit_Detector output.

Input:
- raw detections from Digit_Detector for one amount ROI;
- semantic scope: total_pot / stack / chips.

Output:
- parsed amount value or None;
- all_in flag, which is allowed only for stack ROI;
- parser warnings for malformed symbol sequences.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from config import DIGIT_DETECT_THRESHOLD
from detectors.digit_detector import DigitDetection


DIGIT_CLASS_ALIASES: Dict[str, str] = {
    "dot": ".",
    "period": ".",
    "comma": ".",
    ",": ".",
    "decimal": ".",
    "all_in": "All-in",
    "all-in": "All-in",
    "All_in": "All-in",
    "ALL_IN": "All-in",
    "ALL-IN": "All-in",
}


ALLOWED_SYMBOLS = set("0123456789") | {"."}


def _canonical_class_name(class_name: str) -> str:
    normalized = str(class_name).strip()
    return DIGIT_CLASS_ALIASES.get(normalized, normalized)


def _x_center(detection: DigitDetection) -> float:
    x1, _, x2, _ = detection.bbox_xyxy
    return (float(x1) + float(x2)) / 2.0


def _detected(detection: DigitDetection) -> bool:
    return detection.confidence >= DIGIT_DETECT_THRESHOLD


def parse_digit_amount_detections(
    raw_detections: List[DigitDetection],
    *,
    amount_scope: str,
) -> Tuple[Optional[int | float], bool, List[str]]:
    """
    Parse left-to-right symbols into a numeric amount.

    Rules:
    - only classes 0..9 and '.' participate in number assembly;
    - '.' is used as decimal separator, only the first detected separator is kept;
    - All-in is respected only for stack ROI;
    - if no valid digit sequence exists, return value=None.
    """
    warnings: List[str] = []

    filtered = [d for d in raw_detections if _detected(d)]
    all_in = amount_scope == "stack" and any(
        _canonical_class_name(d.class_name) == "All-in" for d in filtered
    )

    symbol_detections = [
        d
        for d in filtered
        if _canonical_class_name(d.class_name) in ALLOWED_SYMBOLS
    ]
    symbol_detections.sort(key=_x_center)

    symbols: List[str] = []
    decimal_seen = False
    for detection in symbol_detections:
        symbol = _canonical_class_name(detection.class_name)
        if symbol == ".":
            if decimal_seen:
                warnings.append("Duplicate decimal separator ignored.")
                continue
            decimal_seen = True
        symbols.append(symbol)

    if not symbols:
        return None, all_in, warnings

    text_value = "".join(symbols)
    if text_value in {".", ""}:
        warnings.append("Digit sequence does not contain a valid numeric value.")
        return None, all_in, warnings

    if text_value.startswith("."):
        text_value = "0" + text_value
    if text_value.endswith("."):
        text_value = text_value[:-1]
        decimal_seen = False

    try:
        if decimal_seen:
            return float(text_value), all_in, warnings
        return int(text_value), all_in, warnings
    except ValueError:
        warnings.append(f"Unable to parse digit sequence: {text_value!r}.")
        return None, all_in, warnings
