r"""
pipeline/trigger_ui_pipeline.py

PokerVision Core V0.4 — Trigger UI normalization pipeline.

Этот модуль принимает ROI одного table_N, запускает Trigger_UI_Detector,
нормализует классы и возвращает готовый clean JSON-блок trigger_ui.

V0.3 boundaries:
- клики НЕ выполняются;
- Table_Seat_BoardPot_Detector запускается внешним orchestrator-слоем после strong Active;
- Action_Button_Detector НЕ запускается;
- raw bbox НЕ пишется в clean JSON;
- поля confirmed и confidence_level НЕ пишутся в clean JSON;
- внутреннее подтверждение по порогу 0.78 используется только для runtime-логики;
- aliases кривых имён классов нормализуются до канонических имён;
- Active с confidence >= 0.78 только выставляет hint/status ready_for_structure_pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_WARNING,
    TABLE_STATUS_READY_FOR_STRUCTURE_PIPELINE,
    TRIGGER_UI_CLICK_EXECUTION_ENABLED,
    TRIGGER_UI_CONFIRM_THRESHOLD,
    TRIGGER_UI_DETECT_THRESHOLD,
    TRIGGER_UI_ENABLED,
)
from detectors.trigger_ui_detector import TriggerUIDetection, run_trigger_ui_detector
from logic.trigger_ui_policy import TRIGGER_UI_CLASS_ORDER, is_known_trigger_ui_class


# -----------------------------------------------------------------------------
# Alias-normalizer имён классов Trigger_UI_Detector.
#
# Нужен для случаев, когда names в модели или dataset.yaml содержат опечатку,
# например "1_ roll_board" вместо канонического "1_roll_board".
# В clean JSON всегда пишется только каноническое имя класса.
# -----------------------------------------------------------------------------
TRIGGER_UI_CLASS_ALIASES: Dict[str, str] = {
    "1_ roll_board": "1_roll_board",
    "1 roll_board": "1_roll_board",
    "1_roll board": "1_roll_board",
    "1-roll-board": "1_roll_board",
    "1_roll-board": "1_roll_board",
}


@dataclass
class TriggerUIPipelineResult:
    trigger_ui_block: Dict[str, Any]
    table_status_hint: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    # Runtime-only normalized detections with local ROI bbox/confidence.
    # This is intentionally NOT written into clean JSON. It is used only by
    # V1.1 Trigger_UI service-click dry-run/guard logic.
    best_by_class: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _canonical_class_name(class_name: str) -> str:
    """
    Привести имя класса модели к каноническому имени clean JSON.

    Делает минимальную безопасную нормализацию:
    - trim пробелов по краям;
    - замена известных aliases;
    - остальные неизвестные имена не меняет, чтобы не скрывать реальные ошибки модели.
    """
    normalized = str(class_name).strip()
    return TRIGGER_UI_CLASS_ALIASES.get(normalized, normalized)


def _is_detected(confidence: float) -> bool:
    return confidence >= TRIGGER_UI_DETECT_THRESHOLD


def _is_strong_detected_internal(confidence: float) -> bool:
    """
    Runtime-only strong-detect по верхнему порогу.

    В clean JSON поле confirmed намеренно НЕ записывается.
    Это нужно, чтобы JSON оставался компактным и не содержал "confirmed": true/false,
    но внутренняя логика Active -> ready_for_structure_pipeline продолжала работать.
    """
    return confidence >= TRIGGER_UI_CONFIRM_THRESHOLD


def _empty_class_block(class_name: str) -> Dict[str, Any]:
    # Clean JSON V0.5 хранит только class_name/detect без confidence.
    return {
        "class_name": class_name,
        "detect": False,
    }


def _normalize_detection(class_name: str, confidence: float) -> Dict[str, Any]:
    block = _empty_class_block(class_name)

    if _is_detected(confidence):
        block["detect"] = True

    return block


def _best_detection_by_class(raw_detections: List[TriggerUIDetection]) -> Dict[str, TriggerUIDetection]:
    """
    Оставить по одному лучшему detection на каждый канонический класс.

    Если модель вернула несколько bbox одного класса, clean JSON хранит только
    итоговую логическую сводку класса: class_name/detect/confidence.
    Raw bbox в V0.3 не пишем в clean JSON.
    """
    best: Dict[str, TriggerUIDetection] = {}

    for detection in raw_detections:
        canonical_name = _canonical_class_name(detection.class_name)

        if not is_known_trigger_ui_class(canonical_name):
            continue

        current = best.get(canonical_name)
        if current is None or detection.confidence > current.confidence:
            best[canonical_name] = detection

    return best


def _unknown_raw_class_names(raw_detections: List[TriggerUIDetection]) -> List[str]:
    """
    Вернуть только те raw class_name, которые не распознаны даже после alias-normalize.
    """
    unknown = set()

    for detection in raw_detections:
        canonical_name = _canonical_class_name(detection.class_name)
        if not is_known_trigger_ui_class(canonical_name):
            unknown.add(str(detection.class_name))

    return sorted(unknown)


def _thresholds_json() -> Dict[str, float]:
    return {
        "detect": TRIGGER_UI_DETECT_THRESHOLD,
        "strong_detect": TRIGGER_UI_CONFIRM_THRESHOLD,
    }


def build_disabled_trigger_ui_block(reason: str) -> TriggerUIPipelineResult:
    classes = {class_name: _empty_class_block(class_name) for class_name in TRIGGER_UI_CLASS_ORDER}
    block = {
        "status": "skipped",
        "processing_time_ms": 0,
        "model_name": "Trigger_UI_Detector",
        "input_scope": "table_roi",
        "click_execution_enabled": False,
        "thresholds": _thresholds_json(),
        "classes": classes,
        "next_stage_hint": None,
        "reason": reason,
    }
    return TriggerUIPipelineResult(trigger_ui_block=block, warnings=[reason])


def run_trigger_ui_pipeline(table_roi_image: Any, table_id: str) -> TriggerUIPipelineResult:
    """
    Полный Trigger UI stage для одного table_N.

    Возвращает clean trigger_ui block для JSON.

    Самая важная защита V0.3:
    - даже если класс Remove_Game/Exit_cashOut/Bunny/True_active_fold найден,
      этот pipeline НЕ кликает;
    - даже если Active прошёл внутренний strong threshold, pipeline НЕ запускает структуру стола;
    - для Active он только возвращает table_status_hint="ready_for_structure_pipeline";
    - поля confirmed и confidence_level не пишутся в clean JSON;
    - aliases вроде "1_ roll_board" нормализуются в "1_roll_board".
    """
    if not TRIGGER_UI_ENABLED:
        return build_disabled_trigger_ui_block("TRIGGER_UI_ENABLED=False")

    started_at = time.perf_counter()
    warnings: List[str] = []
    errors: List[str] = []
    classes = {class_name: _empty_class_block(class_name) for class_name in TRIGGER_UI_CLASS_ORDER}
    table_status_hint: Optional[str] = None
    next_stage_hint: Optional[str] = "waiting_for_strong_active"

    try:
        raw_detections = run_trigger_ui_detector(table_roi_image)
    except Exception as exc:
        error_message = f"Trigger_UI_Detector failed for {table_id}: {exc}"
        errors.append(error_message)
        block = {
            "status": STATUS_ERROR,
            "processing_time_ms": _elapsed_ms(started_at),
            "model_name": "Trigger_UI_Detector",
            "input_scope": "table_roi",
            "click_execution_enabled": TRIGGER_UI_CLICK_EXECUTION_ENABLED,
            "thresholds": _thresholds_json(),
            "classes": classes,
            "raw_detection_count": 0,
            "next_stage_hint": None,
            "error": error_message,
        }
        return TriggerUIPipelineResult(trigger_ui_block=block, warnings=warnings, errors=errors)

    best_by_class = _best_detection_by_class(raw_detections)
    runtime_best_by_class: Dict[str, Dict[str, Any]] = {}
    for runtime_class_name, runtime_detection in best_by_class.items():
        runtime_best_by_class[runtime_class_name] = {
            "class_id": int(runtime_detection.class_id),
            "class_name": runtime_class_name,
            "raw_class_name": str(runtime_detection.class_name),
            "confidence": float(runtime_detection.confidence),
            "bbox_xyxy": [int(round(value)) for value in runtime_detection.bbox_xyxy],
        }

    unknown_classes = _unknown_raw_class_names(raw_detections)
    if unknown_classes:
        warnings.append(f"{table_id}: unknown Trigger_UI classes ignored in clean JSON: {unknown_classes}")

    weak_detected_classes: List[str] = []
    detected_classes: List[str] = []
    strong_detected_classes: List[str] = []

    for class_name, detection in best_by_class.items():
        # class_name здесь уже канонический: например "1_roll_board".
        normalized = _normalize_detection(class_name, detection.confidence)
        classes[class_name] = normalized

        if _is_detected(detection.confidence):
            detected_classes.append(class_name)

        if _is_detected(detection.confidence) and not _is_strong_detected_internal(detection.confidence):
            weak_detected_classes.append(class_name)
            warnings.append(
                f"{table_id}: {class_name} detect=true but strong_detect=false "
                f"({detection.confidence:.3f} in [{TRIGGER_UI_DETECT_THRESHOLD}, {TRIGGER_UI_CONFIRM_THRESHOLD}))"
            )

        if _is_strong_detected_internal(detection.confidence):
            strong_detected_classes.append(class_name)

    # Active — единственный класс, который в V0.3 может пометить table как готовый
    # к будущему этапу структуры. Но сам Table_Seat_BoardPot_Detector здесь НЕ запускается.
    active_detection = best_by_class.get("Active")
    if active_detection is not None and _is_strong_detected_internal(active_detection.confidence):
        table_status_hint = TABLE_STATUS_READY_FOR_STRUCTURE_PIPELINE
        next_stage_hint = TABLE_STATUS_READY_FOR_STRUCTURE_PIPELINE

    # Non_active_fold явно НЕ запускает структуру в V0.3.
    # Несколько strong-detected классов на одном table_N являются допустимой ситуацией.

    status = STATUS_OK
    if warnings:
        status = STATUS_WARNING
    if errors:
        status = STATUS_ERROR

    block = {
        "status": status,
        "processing_time_ms": _elapsed_ms(started_at),
        "model_name": "Trigger_UI_Detector",
        "input_scope": "table_roi",
        "click_execution_enabled": TRIGGER_UI_CLICK_EXECUTION_ENABLED,
        "thresholds": _thresholds_json(),
        "classes": classes,
        "detected_classes": detected_classes,
        "strong_detected_classes": strong_detected_classes,
        "weak_detected_classes": weak_detected_classes,
        "raw_detection_count": len(raw_detections),
        "next_stage_hint": next_stage_hint,
    }

    return TriggerUIPipelineResult(
        trigger_ui_block=block,
        table_status_hint=table_status_hint,
        warnings=warnings,
        errors=errors,
        best_by_class=runtime_best_by_class,
    )
