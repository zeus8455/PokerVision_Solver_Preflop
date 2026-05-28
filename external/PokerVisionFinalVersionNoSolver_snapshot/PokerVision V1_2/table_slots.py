"""
table_slots.py

PokerVision Core V0.2 — координаты 6 table-областей.

Файл хранит только геометрию table_01 ... table_06.
Он не запускает UI, не анализирует изображения и не создаёт JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


@dataclass(frozen=True)
class SlotBBox:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def w(self) -> int:
        return self.x2 - self.x1

    @property
    def h(self) -> int:
        return self.y2 - self.y1

    def to_json(self) -> Dict[str, int]:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "w": self.w,
            "h": self.h,
        }

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass(frozen=True)
class TableSlot:
    table_id: str
    table_index: int
    bbox: SlotBBox

    def to_json(self) -> Dict[str, object]:
        return {
            "table_id": self.table_id,
            "table_index": self.table_index,
            "slot_bbox": self.bbox.to_json(),
        }


TABLE_SLOTS: Dict[str, TableSlot] = {
    "table_01": TableSlot("table_01", 1, SlotBBox(63, 93, 875, 681)),
    "table_02": TableSlot("table_02", 2, SlotBBox(875, 93, 1686, 681)),
    "table_03": TableSlot("table_03", 3, SlotBBox(1686, 93, 2498, 681)),
    "table_04": TableSlot("table_04", 4, SlotBBox(63, 681, 875, 1269)),
    "table_05": TableSlot("table_05", 5, SlotBBox(875, 681, 1686, 1269)),
    "table_06": TableSlot("table_06", 6, SlotBBox(1686, 681, 2498, 1269)),
}


def validate_table_slots() -> None:
    if len(TABLE_SLOTS) != 6:
        raise ValueError(f"Expected 6 table slots, got {len(TABLE_SLOTS)}")

    seen_ids: Set[str] = set()
    seen_indexes: Set[int] = set()
    seen_bboxes: Set[Tuple[int, int, int, int]] = set()

    for expected_index in range(1, 7):
        expected_id = f"table_{expected_index:02d}"

        if expected_id not in TABLE_SLOTS:
            raise ValueError(f"Missing slot: {expected_id}")

        slot = TABLE_SLOTS[expected_id]

        if slot.table_id != expected_id:
            raise ValueError(
                f"Slot key mismatch: key={expected_id}, slot.table_id={slot.table_id}"
            )

        if slot.table_index != expected_index:
            raise ValueError(
                f"Slot index mismatch: table_id={slot.table_id}, "
                f"expected_index={expected_index}, got={slot.table_index}"
            )

        if slot.table_id in seen_ids:
            raise ValueError(f"Duplicate table_id: {slot.table_id}")

        if slot.table_index in seen_indexes:
            raise ValueError(f"Duplicate table_index: {slot.table_index}")

        bbox_tuple = slot.bbox.as_tuple()

        if bbox_tuple in seen_bboxes:
            raise ValueError(f"Duplicate bbox: {bbox_tuple}")

        seen_ids.add(slot.table_id)
        seen_indexes.add(slot.table_index)
        seen_bboxes.add(bbox_tuple)


validate_table_slots()


def list_table_slots() -> List[TableSlot]:
    validate_table_slots()
    return [TABLE_SLOTS[f"table_{index:02d}"] for index in range(1, 7)]


def get_table_slot(table_id: str) -> TableSlot:
    validate_table_slots()

    if table_id not in TABLE_SLOTS:
        available = ", ".join(TABLE_SLOTS.keys())
        raise KeyError(f"Unknown table_id={table_id!r}. Available: {available}")

    return TABLE_SLOTS[table_id]


def get_table_slot_by_index(table_index: int) -> TableSlot:
    validate_table_slots()

    for slot in TABLE_SLOTS.values():
        if slot.table_index == table_index:
            return slot

    raise KeyError(f"Unknown table_index={table_index!r}. Available range: 1..6")
