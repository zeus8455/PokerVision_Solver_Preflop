r"""
detectors/digit_detector.py

PokerVision Core V0.6 — YOLO wrapper for Digit_Detector.

Responsibility:
- run model inference on ROI of exactly one amount object: Total_pot, Stack or Chips;
- return raw runtime detections for digits 0..9, decimal separator '.' and All-in;
- do not assemble numeric values;
- do not write clean JSON;
- do not click.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    DIGIT_DEVICE,
    DIGIT_INFERENCE_CONF,
    DIGIT_INFERENCE_IMGSZ,
    DIGIT_INFERENCE_IOU,
    DIGIT_MODEL_FILE_NAME,
    DIGIT_MODEL_PATH,
)


@dataclass(frozen=True)
class DigitDetection:
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


def resolve_digit_model_file(model_path: Path = DIGIT_MODEL_PATH) -> Path:
    """Accept either a weights directory or a concrete .pt file."""
    model_path = Path(model_path)
    if model_path.is_dir():
        return model_path / DIGIT_MODEL_FILE_NAME
    return model_path


def load_digit_model(model_path: Path = DIGIT_MODEL_PATH):
    """Lazy-load Digit_Detector once and reuse it for all amount ROI calls."""
    global _CACHED_MODEL, _CACHED_MODEL_PATH

    resolved_path = resolve_digit_model_file(model_path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"Digit_Detector model not found: {resolved_path}")

    if _CACHED_MODEL is not None and _CACHED_MODEL_PATH == resolved_path:
        return _CACHED_MODEL

    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise RuntimeError(
            "Ultralytics is required for Digit_Detector. Install: pip install ultralytics"
        ) from exc

    _CACHED_MODEL = YOLO(str(resolved_path))
    _CACHED_MODEL_PATH = resolved_path
    return _CACHED_MODEL


def run_digit_detector(amount_roi_image: Any) -> List[DigitDetection]:
    """
    Run Digit_Detector on one amount ROI.

    bbox_xyxy stays runtime-only. It is used by the amount parser to order symbols
    from left to right and is not written into clean JSON.
    """
    model = load_digit_model()

    predict_kwargs: Dict[str, Any] = {
        "conf": DIGIT_INFERENCE_CONF,
        "iou": DIGIT_INFERENCE_IOU,
        "imgsz": DIGIT_INFERENCE_IMGSZ,
        "verbose": False,
    }
    if DIGIT_DEVICE is not None:
        predict_kwargs["device"] = DIGIT_DEVICE

    results = model.predict(amount_roi_image, **predict_kwargs)
    if not results:
        return []

    result = results[0]
    names = result.names
    boxes = result.boxes
    detections: List[DigitDetection] = []

    if boxes is None:
        return detections

    for box in boxes:
        class_id = int(box.cls.item())
        confidence = float(box.conf.item())
        class_name = str(names[class_id])
        bbox_xyxy = [float(value) for value in box.xyxy[0].tolist()]
        detections.append(
            DigitDetection(
                class_id=class_id,
                class_name=class_name,
                confidence=confidence,
                bbox_xyxy=bbox_xyxy,
            )
        )

    return detections
