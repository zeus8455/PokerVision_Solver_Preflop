r"""
runtime/table_overlay_status.py

PokerVision Core V1.1 — lightweight per-table runtime status bus for Stage 3 overlay.

The backend updates this in-memory status object after JSON/payload/solver/service/action
runtime stages. ui_display_launch.py reads snapshots and draws a compact overlay over
each table window.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class TableRuntimeStatus:
    table_id: str
    hand_id: Optional[str] = None
    frame_name: Optional[str] = None

    json_status: str = "process"      # process / compile / warning / error
    json_time_ms: Optional[int] = None
    json_path: Optional[str] = None
    json_message: Optional[str] = None

    payload_status: str = "skipped"   # skipped / process / compile / warning / error
    payload_path: Optional[str] = None
    payload_message: Optional[str] = None

    solver_status: str = "skipped"    # skipped / process / stub / ok / timeout / error
    solver_action: Optional[str] = None
    solver_size_pct: Optional[int] = None

    # Action_Button_Detector branch status.
    click_status: str = "skipped"     # skipped / process / dry_run / clicked / blocked / error
    click_target: Optional[str] = None
    click_message: Optional[str] = None

    # Trigger_UI service-click branch status.
    service_click_status: str = "skipped"  # skipped / process / dry_run / clicked / blocked / confirmed / detected_only / error
    service_click_target: Optional[str] = None
    service_click_message: Optional[str] = None
    service_death_card_status: str = "skipped"  # skipped / matched / not_matched / warning / error
    service_death_card_hand_key: Optional[str] = None

    updated_at: Optional[str] = None

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def to_json(self) -> Dict[str, object]:
        return asdict(self)


_STATUS_BY_TABLE_ID: Dict[str, TableRuntimeStatus] = {}


def get_table_runtime_status(table_id: str) -> TableRuntimeStatus:
    if table_id not in _STATUS_BY_TABLE_ID:
        _STATUS_BY_TABLE_ID[table_id] = TableRuntimeStatus(table_id=table_id)
        _STATUS_BY_TABLE_ID[table_id].touch()
    return _STATUS_BY_TABLE_ID[table_id]


def update_table_runtime_status(table_id: str, **kwargs: object) -> TableRuntimeStatus:
    status = get_table_runtime_status(table_id)
    for key, value in kwargs.items():
        if not hasattr(status, key):
            raise AttributeError(f"Unknown TableRuntimeStatus field: {key}")
        setattr(status, key, value)
    status.touch()
    return status


def snapshot_runtime_statuses() -> Dict[str, Dict[str, object]]:
    return {table_id: status.to_json() for table_id, status in sorted(_STATUS_BY_TABLE_ID.items())}


def clear_runtime_statuses() -> None:
    _STATUS_BY_TABLE_ID.clear()
