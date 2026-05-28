r"""
pipeline/action_button_pipeline.py

PokerVision Core V1.1 — Action_Button_Detector normalization pipeline.

Stage boundary:
- input: active table ROI;
- model: Action_Button_Detector;
- output: runtime-only normalized button detections;
- does not write clean JSON;
- does not click.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from config import (
    ACTION_BUTTON_DETECTOR_ENABLED,
    ACTION_BUTTON_DETECT_THRESHOLD,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARNING,
)
from detectors.action_button_detector import ActionButtonDetection, run_action_button_detector
from logic.action_button_policy import (
    ACTION_BUTTON_CLASS_ORDER,
    canonical_action_button_class,
    is_known_action_button_class,
)


@dataclass
class ActionButtonPipelineResult:
    status: str
    detected_classes: List[str] = field(default_factory=list)
    best_by_class: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    raw_detection_count: int = 0
    processing_time_ms: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _detected(confidence: float) -> bool:
    return confidence >= ACTION_BUTTON_DETECT_THRESHOLD


def _bbox_to_int_xyxy(bbox_xyxy: List[float]) -> List[int]:
    if len(bbox_xyxy) != 4:
        raise ValueError(f"Expected bbox with 4 coordinates, got: {bbox_xyxy}")
    x1, y1, x2, y2 = bbox_xyxy
    return [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))]


def _best_detection_by_class(raw_detections: List[ActionButtonDetection]) -> Dict[str, ActionButtonDetection]:
    best: Dict[str, ActionButtonDetection] = {}
    for detection in raw_detections:
        canonical_name = canonical_action_button_class(detection.class_name)
        if not is_known_action_button_class(canonical_name):
            continue
        current = best.get(canonical_name)
        if current is None or detection.confidence > current.confidence:
            best[canonical_name] = detection
    return best


def _unknown_raw_class_names(raw_detections: List[ActionButtonDetection]) -> List[str]:
    unknown = set()
    for detection in raw_detections:
        canonical_name = canonical_action_button_class(detection.class_name)
        if not is_known_action_button_class(canonical_name):
            unknown.add(str(detection.class_name))
    return sorted(unknown)


def build_skipped_action_button_result(reason: str) -> ActionButtonPipelineResult:
    return ActionButtonPipelineResult(
        status=STATUS_SKIPPED,
        warnings=[reason] if reason else [],
    )


def run_action_button_pipeline(*, table_roi_image: Any, active_confirmed: bool) -> ActionButtonPipelineResult:
    started_at = time.perf_counter()

    if not ACTION_BUTTON_DETECTOR_ENABLED:
        return build_skipped_action_button_result("Action_Button_Detector is disabled by config.")

    if not active_confirmed:
        return build_skipped_action_button_result("Active is not confirmed for this table; action buttons skipped.")

    warnings: List[str] = []
    errors: List[str] = []

    try:
        raw_detections = run_action_button_detector(table_roi_image)
        best_raw = _best_detection_by_class(raw_detections)
        unknown = _unknown_raw_class_names(raw_detections)
        if unknown:
            warnings.append(f"unknown Action_Button_Detector classes ignored: {unknown}")

        best_by_class: Dict[str, Dict[str, Any]] = {}
        detected_classes: List[str] = []

        for class_name in ACTION_BUTTON_CLASS_ORDER:
            detection = best_raw.get(class_name)
            if detection is None or not _detected(detection.confidence):
                continue
            detected_classes.append(class_name)
            best_by_class[class_name] = {
                "class_name": class_name,
                "confidence": float(detection.confidence),
                "bbox_xyxy": _bbox_to_int_xyxy(detection.bbox_xyxy),
            }

        status = STATUS_OK if detected_classes else STATUS_WARNING
        if not detected_classes:
            warnings.append("Action_Button_Detector returned no classes above threshold.")

        return ActionButtonPipelineResult(
            status=status,
            detected_classes=detected_classes,
            best_by_class=best_by_class,
            raw_detection_count=len(raw_detections),
            processing_time_ms=_elapsed_ms(started_at),
            warnings=warnings,
            errors=errors,
        )

    except Exception as exc:
        errors.append(str(exc))
        return ActionButtonPipelineResult(
            status=STATUS_ERROR,
            detected_classes=[],
            best_by_class={},
            raw_detection_count=0,
            processing_time_ms=_elapsed_ms(started_at),
            warnings=warnings,
            errors=errors,
        )
