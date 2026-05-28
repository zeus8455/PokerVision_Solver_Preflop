r"""
detectors/player_state_detector.py

PokerVision Core V0.5 — YOLO wrapper for Player_State_Detector.

Responsibility:
- run model inference on ROI of exactly one Player_seatN;
- return raw runtime detections for Stack, Chips, Fold, SitOut, BTN;
- do not decide positions;
- do not write clean JSON;
- do not click.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    PLAYER_STATE_DEVICE,
    PLAYER_STATE_INFERENCE_CONF,
    PLAYER_STATE_INFERENCE_IMGSZ,
    PLAYER_STATE_INFERENCE_IOU,
    PLAYER_STATE_MODEL_FILE_NAME,
    PLAYER_STATE_MODEL_PATH,
)


@dataclass(frozen=True)
class PlayerStateDetection:
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


def resolve_player_state_model_file(model_path: Path = PLAYER_STATE_MODEL_PATH) -> Path:
    model_path = Path(model_path)
    if model_path.is_dir():
        return model_path / PLAYER_STATE_MODEL_FILE_NAME
    return model_path


def load_player_state_model(model_path: Path = PLAYER_STATE_MODEL_PATH):
    """
    Lazy-load Player_State_Detector once and reuse it for all Player_seat ROI calls.
    """
    global _CACHED_MODEL, _CACHED_MODEL_PATH

    resolved_path = resolve_player_state_model_file(model_path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"Player_State_Detector model not found: {resolved_path}")

    if _CACHED_MODEL is not None and _CACHED_MODEL_PATH == resolved_path:
        return _CACHED_MODEL

    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise RuntimeError(
            "Ultralytics is required for Player_State_Detector. Install: pip install ultralytics"
        ) from exc

    _CACHED_MODEL = YOLO(str(resolved_path))
    _CACHED_MODEL_PATH = resolved_path
    return _CACHED_MODEL


def run_player_state_detector(player_seat_roi_image: Any) -> List[PlayerStateDetection]:
    """
    Run Player_State_Detector on one Player_seat ROI.

    bbox_xyxy is runtime-only data. It is not written into clean JSON V0.5.
    """
    model = load_player_state_model()

    predict_kwargs: Dict[str, Any] = {
        "conf": PLAYER_STATE_INFERENCE_CONF,
        "iou": PLAYER_STATE_INFERENCE_IOU,
        "imgsz": PLAYER_STATE_INFERENCE_IMGSZ,
        "verbose": False,
    }
    if PLAYER_STATE_DEVICE is not None:
        predict_kwargs["device"] = PLAYER_STATE_DEVICE

    results = model.predict(player_seat_roi_image, **predict_kwargs)

    detections: List[PlayerStateDetection] = []

    for result in results:
        names = getattr(result, "names", {}) or {}
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue

        for box in boxes:
            class_id = int(box.cls[0].item())
            class_name = str(names.get(class_id, class_id))
            confidence = float(box.conf[0].item())
            xyxy = box.xyxy[0].tolist()

            detections.append(
                PlayerStateDetection(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=confidence,
                    bbox_xyxy=[float(value) for value in xyxy],
                )
            )

    return detections
