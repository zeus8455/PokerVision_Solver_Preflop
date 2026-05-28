r"""
detectors/table_seat_boardpot_detector.py

PokerVision Core V0.4 — YOLO wrapper for Table_Seat_BoardPot_Detector.

Responsibility:
- run model inference on ROI of exactly one table_N;
- return raw runtime detections for Player_seat1..6, Board, Total_pot;
- do not decide table format;
- do not run Player_State_Detector, Card_Detector, Digit_Detector;
- do not write clean JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    TABLE_STRUCTURE_DEVICE,
    TABLE_STRUCTURE_INFERENCE_CONF,
    TABLE_STRUCTURE_INFERENCE_IMGSZ,
    TABLE_STRUCTURE_INFERENCE_IOU,
    TABLE_STRUCTURE_MODEL_FILE_NAME,
    TABLE_STRUCTURE_MODEL_PATH,
)


@dataclass(frozen=True)
class TableStructureDetection:
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


def resolve_table_structure_model_file(model_path: Path = TABLE_STRUCTURE_MODEL_PATH) -> Path:
    model_path = Path(model_path)
    if model_path.is_dir():
        return model_path / TABLE_STRUCTURE_MODEL_FILE_NAME
    return model_path


def load_table_structure_model(model_path: Path = TABLE_STRUCTURE_MODEL_PATH):
    """
    Lazy-load Table_Seat_BoardPot_Detector.

    The model is cached once and reused for all table_01..table_06 ROI calls.
    """
    global _CACHED_MODEL, _CACHED_MODEL_PATH

    resolved_path = resolve_table_structure_model_file(model_path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"Table_Seat_BoardPot_Detector model not found: {resolved_path}")

    if _CACHED_MODEL is not None and _CACHED_MODEL_PATH == resolved_path:
        return _CACHED_MODEL

    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise RuntimeError(
            "Ultralytics is required for Table_Seat_BoardPot_Detector. Install: pip install ultralytics"
        ) from exc

    _CACHED_MODEL = YOLO(str(resolved_path))
    _CACHED_MODEL_PATH = resolved_path
    return _CACHED_MODEL


def run_table_structure_detector(table_roi_image: Any) -> List[TableStructureDetection]:
    """
    Run Table_Seat_BoardPot_Detector on one table ROI.

    bbox_xyxy is kept as runtime data for the structure pipeline because it is required
    to create Board/Total_pot/player_seat processing regions for the next stages.
    """
    model = load_table_structure_model()

    predict_kwargs: Dict[str, Any] = {
        "conf": TABLE_STRUCTURE_INFERENCE_CONF,
        "iou": TABLE_STRUCTURE_INFERENCE_IOU,
        "imgsz": TABLE_STRUCTURE_INFERENCE_IMGSZ,
        "verbose": False,
    }
    if TABLE_STRUCTURE_DEVICE is not None:
        predict_kwargs["device"] = TABLE_STRUCTURE_DEVICE

    results = model.predict(table_roi_image, **predict_kwargs)

    detections: List[TableStructureDetection] = []

    for result in results:
        names = getattr(result, "names", {}) or {}
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue

        for box in boxes:
            class_id = int(box.cls[0].item())
            class_name = str(names.get(class_id, class_id))
            confidence = float(box.conf[0].item())
            xyxy = [float(v) for v in box.xyxy[0].tolist()]

            detections.append(
                TableStructureDetection(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=confidence,
                    bbox_xyxy=xyxy,
                )
            )

    return detections
