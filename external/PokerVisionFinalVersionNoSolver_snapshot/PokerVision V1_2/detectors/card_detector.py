r"""
detectors/card_detector.py

PokerVision Core V0.6 — YOLO wrapper for Card_Detector.

Responsibility:
- run model inference on ROI of exactly one card source: Board or HERO seat;
- return raw runtime detections for the 52 card classes;
- do not decide street;
- do not validate duplicate cards;
- do not write clean JSON;
- do not click.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    CARD_DEVICE,
    CARD_INFERENCE_CONF,
    CARD_INFERENCE_IMGSZ,
    CARD_INFERENCE_IOU,
    CARD_MODEL_FILE_NAME,
    CARD_MODEL_PATH,
)


@dataclass(frozen=True)
class CardDetection:
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


def resolve_card_model_file(model_path: Path = CARD_MODEL_PATH) -> Path:
    """Accept either a weights directory or a concrete .pt file."""
    model_path = Path(model_path)
    if model_path.is_dir():
        return model_path / CARD_MODEL_FILE_NAME
    return model_path


def load_card_model(model_path: Path = CARD_MODEL_PATH):
    """Lazy-load Card_Detector once and reuse it for all Board/HERO ROI calls."""
    global _CACHED_MODEL, _CACHED_MODEL_PATH

    resolved_path = resolve_card_model_file(model_path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"Card_Detector model not found: {resolved_path}")

    if _CACHED_MODEL is not None and _CACHED_MODEL_PATH == resolved_path:
        return _CACHED_MODEL

    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise RuntimeError(
            "Ultralytics is required for Card_Detector. Install: pip install ultralytics"
        ) from exc

    _CACHED_MODEL = YOLO(str(resolved_path))
    _CACHED_MODEL_PATH = resolved_path
    return _CACHED_MODEL


def run_card_detector(card_roi_image: Any) -> List[CardDetection]:
    """
    Run Card_Detector on one Board/HERO ROI.

    bbox_xyxy stays runtime-only. It is used by card policy logic to order cards
    from left to right and is not written into clean JSON.
    """
    model = load_card_model()

    predict_kwargs: Dict[str, Any] = {
        "conf": CARD_INFERENCE_CONF,
        "iou": CARD_INFERENCE_IOU,
        "imgsz": CARD_INFERENCE_IMGSZ,
        "verbose": False,
    }
    if CARD_DEVICE is not None:
        predict_kwargs["device"] = CARD_DEVICE

    results = model.predict(card_roi_image, **predict_kwargs)
    if not results:
        return []

    result = results[0]
    names = getattr(result, "names", {}) or getattr(model, "names", {}) or {}
    boxes = getattr(result, "boxes", None)
    detections: List[CardDetection] = []

    if boxes is None:
        return detections

    for box in boxes:
        class_id = int(box.cls[0].item())
        confidence = float(box.conf[0].item())
        class_name = str(names.get(class_id, class_id))
        bbox_xyxy = [float(value) for value in box.xyxy[0].tolist()]
        detections.append(
            CardDetection(
                class_id=class_id,
                class_name=class_name,
                confidence=confidence,
                bbox_xyxy=bbox_xyxy,
            )
        )

    return detections
