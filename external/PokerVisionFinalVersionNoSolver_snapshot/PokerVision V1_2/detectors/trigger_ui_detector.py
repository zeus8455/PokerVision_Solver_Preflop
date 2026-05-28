r"""
detectors/trigger_ui_detector.py

PokerVision Core V0.4 — обёртка над Trigger_UI_Detector.

Этот модуль делает только одно: запускает YOLO inference по ROI одного table_N
и возвращает raw detections в runtime-формате.

Что модуль НЕ делает:
- не принимает решения о кликах;
- не запускает Table_Seat_BoardPot_Detector;
- не пишет clean JSON;
- не хранит bbox в clean JSON;
- не решает, какой класс важнее.

Дальше raw detections передаются в pipeline/trigger_ui_pipeline.py,
где применяется confidence-нормализация 0.70/0.78 и policy-логика классов.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    TRIGGER_UI_DEVICE,
    TRIGGER_UI_INFERENCE_CONF,
    TRIGGER_UI_INFERENCE_IMGSZ,
    TRIGGER_UI_INFERENCE_IOU,
    TRIGGER_UI_MODEL_FILE_NAME,
    TRIGGER_UI_MODEL_PATH,
)


@dataclass(frozen=True)
class TriggerUIDetection:
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: List[float]

    def to_raw_json(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "bbox_xyxy": self.bbox_xyxy,
        }


_CACHED_MODEL = None
_CACHED_MODEL_PATH: Optional[Path] = None


def resolve_trigger_ui_model_file(model_path: Path = TRIGGER_UI_MODEL_PATH) -> Path:
    r"""
    Принять путь к папке weights или к конкретному .pt файлу.

    Пользователь указал:
    C:\PokerVision\AI_detect\Trigger_UI_Detector\weights

    Поэтому если передана папка, автоматически берём best.pt.
    """
    model_path = Path(model_path)
    if model_path.is_dir():
        return model_path / TRIGGER_UI_MODEL_FILE_NAME
    return model_path


def load_trigger_ui_model(model_path: Path = TRIGGER_UI_MODEL_PATH):
    """
    Lazy-load YOLO модели.

    Модель кэшируется, чтобы не загружать best.pt заново для каждого table_N.
    Это важно для 6-table цикла: модель должна загрузиться один раз, потом работать
    по ROI каждого стола.
    """
    global _CACHED_MODEL, _CACHED_MODEL_PATH

    resolved_path = resolve_trigger_ui_model_file(model_path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"Trigger_UI_Detector model not found: {resolved_path}")

    if _CACHED_MODEL is not None and _CACHED_MODEL_PATH == resolved_path:
        return _CACHED_MODEL

    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise RuntimeError(
            "Ultralytics is required for Trigger_UI_Detector. Install: pip install ultralytics"
        ) from exc

    _CACHED_MODEL = YOLO(str(resolved_path))
    _CACHED_MODEL_PATH = resolved_path
    return _CACHED_MODEL


def run_trigger_ui_detector(table_roi_image: Any) -> List[TriggerUIDetection]:
    """
    Запустить Trigger_UI_Detector на ROI одного стола.

    table_roi_image обычно является PIL.Image, полученным через screenshot.crop(slot_bbox).
    В clean JSON пойдут только class_name/confidence/detect/confirmed.
    bbox_xyxy возвращается из этого модуля только как raw runtime-данные и может быть
    использован позже для debug/click-guard, но НЕ пишется в clean JSON V0.4.
    """
    model = load_trigger_ui_model()

    predict_kwargs: Dict[str, Any] = {
        "conf": TRIGGER_UI_INFERENCE_CONF,
        "iou": TRIGGER_UI_INFERENCE_IOU,
        "imgsz": TRIGGER_UI_INFERENCE_IMGSZ,
        "verbose": False,
    }
    if TRIGGER_UI_DEVICE is not None:
        predict_kwargs["device"] = TRIGGER_UI_DEVICE

    results = model.predict(table_roi_image, **predict_kwargs)

    detections: List[TriggerUIDetection] = []
    if not results:
        return detections

    result = results[0]
    names = getattr(result, "names", {}) or getattr(model, "names", {}) or {}
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return detections

    for box in boxes:
        class_id = int(box.cls[0].item())
        confidence = float(box.conf[0].item())
        class_name = str(names.get(class_id, class_id))
        bbox_xyxy = [float(v) for v in box.xyxy[0].tolist()]

        detections.append(
            TriggerUIDetection(
                class_id=class_id,
                class_name=class_name,
                confidence=confidence,
                bbox_xyxy=bbox_xyxy,
            )
        )

    return detections
