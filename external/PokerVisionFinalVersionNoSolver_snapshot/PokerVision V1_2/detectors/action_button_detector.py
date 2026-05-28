r"""
detectors/action_button_detector.py

PokerVision Core V1.1 — YOLO wrapper for Action_Button_Detector.

Responsibility:
- run model inference on ROI of exactly one active table_N;
- return raw runtime detections for action buttons;
- do not decide which action is correct;
- do not click;
- do not write clean JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    ACTION_BUTTON_DEVICE,
    ACTION_BUTTON_INFERENCE_CONF,
    ACTION_BUTTON_INFERENCE_IMGSZ,
    ACTION_BUTTON_INFERENCE_IOU,
    ACTION_BUTTON_MODEL_FILE_NAME,
    ACTION_BUTTON_MODEL_PATH,
)


@dataclass(frozen=True)
class ActionButtonDetection:
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


def resolve_action_button_model_file(model_path: Path = ACTION_BUTTON_MODEL_PATH) -> Path:
    """Accept either a weights directory or a concrete .pt file."""
    model_path = Path(model_path)
    if model_path.is_dir():
        return model_path / ACTION_BUTTON_MODEL_FILE_NAME
    return model_path


def load_action_button_model(model_path: Path = ACTION_BUTTON_MODEL_PATH):
    """Lazy-load Action_Button_Detector once and reuse it for all active table ROI calls."""
    global _CACHED_MODEL, _CACHED_MODEL_PATH

    resolved_path = resolve_action_button_model_file(model_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Action_Button_Detector model not found: {resolved_path}")

    if _CACHED_MODEL is not None and _CACHED_MODEL_PATH == resolved_path:
        return _CACHED_MODEL

    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise RuntimeError(
            "Ultralytics is required for Action_Button_Detector. Install: pip install ultralytics"
        ) from exc

    _CACHED_MODEL = YOLO(str(resolved_path))
    _CACHED_MODEL_PATH = resolved_path
    return _CACHED_MODEL


def run_action_button_detector(table_roi_image: Any) -> List[ActionButtonDetection]:
    """
    Run Action_Button_Detector on one active table ROI.

    bbox_xyxy is runtime-only local ROI data. It must be mapped to global monitor
    coordinates by the click runtime through the current table slot bbox.
    """
    model = load_action_button_model()

    predict_kwargs: Dict[str, Any] = {
        "conf": ACTION_BUTTON_INFERENCE_CONF,
        "iou": ACTION_BUTTON_INFERENCE_IOU,
        "imgsz": ACTION_BUTTON_INFERENCE_IMGSZ,
        "verbose": False,
    }
    if ACTION_BUTTON_DEVICE is not None:
        predict_kwargs["device"] = ACTION_BUTTON_DEVICE

    results = model.predict(table_roi_image, **predict_kwargs)
    detections: List[ActionButtonDetection] = []
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
        bbox_xyxy = [float(value) for value in box.xyxy[0].tolist()]
        detections.append(
            ActionButtonDetection(
                class_id=class_id,
                class_name=class_name,
                confidence=confidence,
                bbox_xyxy=bbox_xyxy,
            )
        )

    return detections
