r"""
json_state.py

PokerVision Core V1 — clean JSON Builder.

V1 identity contract:
- table.hand_id = базовая раздача: hand_01, hand_02, ...;
- table.frame_name = имя конкретного кадра/JSON:
  hand_01_preflop, hand_01_flop, hand_08_preflop_02, ...;
- table.frame_id = table_id + frame_name;
- output JSON filename = frame_name.json внутри своей папки table_N.

Так одна и та же раздача сохраняет один hand_id на всех улицах, но каждый кадр
получает собственное имя файла, совпадающее с новым V1 test naming contract.
"""

from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    ATOMIC_JSON_WRITE,
    PREVENT_OUTPUT_PATH_ESCAPE,
    SCHEMA_VERSION,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_VALUES,
    VALIDATE_JSON_IDENTITY_BEFORE_SAVE,
    assert_path_inside,
    validate_status,
)
from table_slots import TableSlot




def now_perf_counter() -> float:
    return time.perf_counter()


def elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def clone_json_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(state)


def build_pipeline_meta(
    status: str,
    processing_time_ms: int,
    note: str,
    cycle_id: str,
) -> Dict[str, Any]:
    validate_status(status)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "processing_time_ms": processing_time_ms,
        "status_values": list(STATUS_VALUES),
        "cycle_id": cycle_id,
        "note": note,
    }


def build_table_block(
    slot: TableSlot,
    hand_id: str,
    frame_name: str,
    processing_time_ms: int,
    table_status: str = STATUS_OK,
) -> Dict[str, Any]:
    frame_id = f"{slot.table_id}_{frame_name}"

    return {
        "status": table_status,
        "processing_time_ms": processing_time_ms,
        "frame_id": frame_id,
        "frame_name": frame_name,
        "table_id": slot.table_id,
        "table_index": slot.table_index,
        "hand_id": hand_id,
        "slot_bbox": slot.bbox.to_json(),
    }


def build_table_frame_state(
    slot: TableSlot,
    hand_id: str,
    frame_name: str,
    cycle_id: str,
    processing_time_ms: int,
    trigger_ui_block: Optional[Dict[str, Any]] = None,
    table_structure_block: Optional[Dict[str, Any]] = None,
    players_block: Optional[Dict[str, Any]] = None,
    table_status: str = STATUS_OK,
) -> Dict[str, Any]:
    """
    Собрать clean JSON для одного table/frame.

    Никакие fake seat/board/pot/players блоки здесь не создаются.
    Блок пишется только если соответствующий pipeline реально построил результат.
    """
    state: Dict[str, Any] = {
        "pipeline_meta": build_pipeline_meta(
            status=STATUS_OK,
            processing_time_ms=processing_time_ms,
            note=(
                "Table state JSON created after current V1 runtime hand tracking + "
                "Trigger UI + table structure + compact players + digit amounts + "
                "card detection processing cycle."
            ),
            cycle_id=cycle_id,
        ),
        "table": build_table_block(
            slot=slot,
            hand_id=hand_id,
            frame_name=frame_name,
            processing_time_ms=processing_time_ms,
            table_status=table_status,
        ),
        "errors": [],
        "warnings": [],
    }

    if trigger_ui_block is not None:
        state["trigger_ui"] = trigger_ui_block

    if table_structure_block is not None:
        state["table_structure"] = table_structure_block

    if players_block is not None:
        state["players"] = players_block

    return state


def add_warning(
    state: Dict[str, Any],
    block: str,
    message: str,
    warning_type: str = "Warning",
) -> None:
    state.setdefault("warnings", []).append(
        {
            "block": block,
            "type": warning_type,
            "message": message,
        }
    )

    if "pipeline_meta" in state and state["pipeline_meta"].get("status") == STATUS_OK:
        state["pipeline_meta"]["status"] = "warning"


def add_error(
    state: Dict[str, Any],
    block: str,
    message: str,
    error_type: str = "Error",
) -> None:
    state.setdefault("errors", []).append(
        {
            "block": block,
            "type": error_type,
            "message": message,
        }
    )

    if "pipeline_meta" in state:
        state["pipeline_meta"]["status"] = STATUS_ERROR


def assert_json_identity(
    state: Dict[str, Any],
    expected_table_id: str,
    expected_hand_id: str,
    expected_frame_name: str,
) -> None:
    if "table" not in state:
        raise ValueError("JSON state has no table block")

    table = state["table"]
    expected_frame_id = f"{expected_table_id}_{expected_frame_name}"

    if table.get("table_id") != expected_table_id:
        raise ValueError(
            f"JSON table_id mismatch: expected={expected_table_id}, got={table.get('table_id')}"
        )

    if table.get("hand_id") != expected_hand_id:
        raise ValueError(
            f"JSON hand_id mismatch: expected={expected_hand_id}, got={table.get('hand_id')}"
        )

    if table.get("frame_name") != expected_frame_name:
        raise ValueError(
            f"JSON frame_name mismatch: expected={expected_frame_name}, got={table.get('frame_name')}"
        )

    if table.get("frame_id") != expected_frame_id:
        raise ValueError(
            f"JSON frame_id mismatch: expected={expected_frame_id}, got={table.get('frame_id')}"
        )


def build_table_json_output_path(
    cycle_dir: Path,
    table_id: str,
    frame_name: str,
) -> Path:
    return cycle_dir / table_id / f"{frame_name}.json"


def assert_output_path_identity(
    output_path: Path,
    cycle_dir: Path,
    table_id: str,
    frame_name: str,
) -> None:
    if PREVENT_OUTPUT_PATH_ESCAPE:
        assert_path_inside(output_path, cycle_dir)

    if output_path.parent.name != table_id:
        raise ValueError(
            f"Output parent dir mismatch: expected={table_id}, got={output_path.parent.name}"
        )

    expected_file_name = f"{frame_name}.json"
    if output_path.name != expected_file_name:
        raise ValueError(
            f"Output file mismatch: expected={expected_file_name}, got={output_path.name}"
        )


def save_json_atomic(state: Dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if ATOMIC_JSON_WRITE:
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp_path, output_path)
    else:
        output_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return output_path



def save_table_frame_json(
    state: Dict[str, Any],
    cycle_dir: Path,
    table_id: str,
    hand_id: str,
    frame_name: str,
) -> Path:
    safe_state = clone_json_state(state)

    output_path = build_table_json_output_path(
        cycle_dir=cycle_dir,
        table_id=table_id,
        frame_name=frame_name,
    )

    if VALIDATE_JSON_IDENTITY_BEFORE_SAVE:
        assert_json_identity(
            state=safe_state,
            expected_table_id=table_id,
            expected_hand_id=hand_id,
            expected_frame_name=frame_name,
        )
        assert_output_path_identity(
            output_path=output_path,
            cycle_dir=cycle_dir,
            table_id=table_id,
            frame_name=frame_name,
        )

    return save_json_atomic(state=safe_state, output_path=output_path)


