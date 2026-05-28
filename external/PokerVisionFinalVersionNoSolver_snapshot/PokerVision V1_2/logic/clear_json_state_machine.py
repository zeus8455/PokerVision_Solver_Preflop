r"""
clear_json_state_machine.py

PokerVision Clear_JSON state-machine.

Purpose:
- Accept already-built minimal Clear_JSON objects.
- Decide whether the Clear_JSON represents a new poker-state worth saving.
- Assign stable street occurrence indexes: preflop_01, preflop_02, flop_01, ...
- Keep this layer independent from detector/runtime/debug data.

This module does NOT build Clear_JSON from Dark_JSON. Use:
    logic.clear_json_builder.build_clear_json_from_dark_state(...)

This module does NOT restore missing players/stacks/chips. Use logic.clear_json_recovery before observe(...).
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from logic.clear_json_builder import validate_clear_json_contract


_VALID_STREETS = {"preflop", "flop", "turn", "river"}
_SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_\-]+")


@dataclass(frozen=True)
class ClearJsonStateDecision:
    should_save: bool
    reason: str
    table_id: str
    hand_id: str
    street: Optional[str]
    street_occurrence: Optional[int]
    frame_id: Optional[str]
    previous_frame_id: Optional[str] = None
    signature: Optional[str] = None
    previous_signature: Optional[str] = None
    validation_ok: bool = True
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        return {
            "state_machine_version": "clear_json_state_machine_v2_2026_05_15",
            "should_save": self.should_save,
            "reason": self.reason,
            "table_id": self.table_id,
            "hand_id": self.hand_id,
            "street": self.street,
            "street_occurrence": self.street_occurrence,
            "frame_id": self.frame_id,
            "previous_frame_id": self.previous_frame_id,
            "signature": self.signature,
            "previous_signature": self.previous_signature,
            "validation_ok": self.validation_ok,
            "validation_errors": list(self.validation_errors),
            "validation_warnings": list(self.validation_warnings),
        }


@dataclass
class _TrackedClearJsonTableState:
    hand_id: str
    last_clear_json: Optional[Dict[str, Any]] = None
    last_signature: Optional[str] = None
    last_frame_id: Optional[str] = None
    current_street: Optional[str] = None
    street_counts: Dict[str, int] = field(default_factory=dict)


class ClearJsonStateMachine:
    """
    State-machine for Clear_JSON persistence.

    Rules:
    - New hand: reset street counters and save first state as *_01.
    - Same hand + same semantic Clear_JSON signature: skip duplicate.
    - Same hand + changed signature on same street: save next street occurrence.
    - Same hand + new street: save first occurrence for that street.

    Important:
    Duplicate comparison intentionally ignores frame_id, because frame_id is assigned
    by this state-machine. Otherwise the same poker-state with a generated *_01 id
    would not match the next candidate coming from the builder.
    """

    def __init__(self) -> None:
        self._state_by_table_id: Dict[str, _TrackedClearJsonTableState] = {}

    @staticmethod
    def _normalize_text(value: Any) -> str:
        text = str(value).strip() if value is not None else ""
        text = _SAFE_TOKEN_RE.sub("_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text

    @staticmethod
    def _extract_street(clear_json: Dict[str, Any]) -> Optional[str]:
        board = clear_json.get("board")
        if not isinstance(board, dict):
            return None
        street = board.get("street")
        if street is None:
            return None
        normalized = str(street).strip().lower()
        return normalized if normalized in _VALID_STREETS else None

    @staticmethod
    def _safe_suffix_street(street: Optional[str]) -> str:
        if street is None:
            return "unknown"
        value = str(street).strip().lower()
        return value if value in _VALID_STREETS else "unknown"

    @staticmethod
    def build_frame_id(table_id: str, hand_id: str, street: Optional[str], occurrence: Optional[int]) -> str:
        """Build stable Clear_JSON frame_id with explicit _NN index, including _01."""
        safe_table = ClearJsonStateMachine._normalize_text(table_id) or "table_unknown"
        safe_hand = ClearJsonStateMachine._normalize_text(hand_id) or "hand_unknown"
        safe_street = ClearJsonStateMachine._safe_suffix_street(street)
        safe_occurrence = max(1, int(occurrence or 1))
        return f"{safe_table}_{safe_hand}_{safe_street}_{safe_occurrence:02d}"

    @staticmethod
    def _copy_with_frame_id(clear_json: Dict[str, Any], frame_id: str) -> Dict[str, Any]:
        out = dict(clear_json)
        out["frame_id"] = frame_id
        return out

    @staticmethod
    def _semantic_signature(clear_json: Dict[str, Any]) -> str:
        """Canonical poker-state signature that ignores generated frame_id."""
        payload = dict(clear_json)
        payload.pop("frame_id", None)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def reset_table(self, table_id: str) -> None:
        """Forget tracked Clear_JSON history for a table."""
        self._state_by_table_id.pop(str(table_id), None)

    def reset_all(self) -> None:
        """Forget all tracked Clear_JSON history."""
        self._state_by_table_id.clear()

    def get_last_clear_json(self, table_id: str, hand_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return a copy of the last stable Clear_JSON for table/hand, if any.

        The recovery layer uses this as previous stable state. A hand_id mismatch
        returns None to prevent accidental recovery across hands.
        """
        table_id_clean = self._normalize_text(table_id) or "table_unknown"
        tracked = self._state_by_table_id.get(table_id_clean)
        if tracked is None or tracked.last_clear_json is None:
            return None
        if hand_id is not None:
            hand_id_clean = self._normalize_text(hand_id) or "hand_unknown"
            if tracked.hand_id != hand_id_clean:
                return None
        return deepcopy(tracked.last_clear_json)

    def observe(
        self,
        *,
        table_id: str,
        hand_id: str,
        clear_json: Dict[str, Any],
    ) -> Tuple[ClearJsonStateDecision, Optional[Dict[str, Any]]]:
        """
        Observe one Clear_JSON candidate.

        Returns:
            (decision, clear_json_to_save_or_none)

        If decision.should_save is True, returned Clear_JSON already contains the
        final state-machine frame_id. If False, returned value is None.
        """
        table_id_clean = self._normalize_text(table_id) or "table_unknown"
        hand_id_clean = self._normalize_text(hand_id) or "hand_unknown"
        street = self._extract_street(clear_json)

        validation = validate_clear_json_contract(clear_json)
        validation_ok = bool(validation.get("ok", False)) if isinstance(validation, dict) else False
        validation_errors = [str(item) for item in validation.get("errors", [])] if isinstance(validation, dict) else ["invalid validation result"]
        validation_warnings = [str(item) for item in validation.get("warnings", [])] if isinstance(validation, dict) else []

        if not validation_ok:
            return (
                ClearJsonStateDecision(
                    should_save=False,
                    reason="clear_json_contract_validation_failed",
                    table_id=table_id_clean,
                    hand_id=hand_id_clean,
                    street=street,
                    street_occurrence=None,
                    frame_id=None,
                    validation_ok=False,
                    validation_errors=validation_errors,
                    validation_warnings=validation_warnings,
                ),
                None,
            )

        tracked = self._state_by_table_id.get(table_id_clean)
        new_hand = tracked is None or tracked.hand_id != hand_id_clean
        if new_hand:
            tracked = _TrackedClearJsonTableState(hand_id=hand_id_clean)
            self._state_by_table_id[table_id_clean] = tracked

        signature = self._semantic_signature(clear_json)

        if not new_hand and signature == tracked.last_signature:
            return (
                ClearJsonStateDecision(
                    should_save=False,
                    reason="duplicate_clear_json_state_blocked",
                    table_id=table_id_clean,
                    hand_id=hand_id_clean,
                    street=street,
                    street_occurrence=tracked.street_counts.get(street or "", None),
                    frame_id=None,
                    previous_frame_id=tracked.last_frame_id,
                    signature=signature,
                    previous_signature=tracked.last_signature,
                    validation_ok=True,
                    validation_errors=[],
                    validation_warnings=validation_warnings,
                ),
                None,
            )

        previous_frame_id = tracked.last_frame_id
        previous_signature = tracked.last_signature
        previous_street = tracked.current_street

        if street is None:
            occurrence = 1
        else:
            occurrence = tracked.street_counts.get(street, 0) + 1
            tracked.street_counts[street] = occurrence

        final_frame_id = self.build_frame_id(table_id_clean, hand_id_clean, street, occurrence)
        clear_to_save = self._copy_with_frame_id(clear_json, final_frame_id)

        tracked.last_clear_json = clear_to_save
        tracked.last_signature = signature
        tracked.last_frame_id = final_frame_id
        tracked.current_street = street

        if new_hand:
            reason = "new_hand_first_clear_json_state"
        elif previous_signature is None:
            reason = "first_clear_json_state"
        elif previous_street != street and occurrence == 1:
            reason = "new_street_clear_json_state"
        else:
            reason = "changed_clear_json_state"

        decision = ClearJsonStateDecision(
            should_save=True,
            reason=reason,
            table_id=table_id_clean,
            hand_id=hand_id_clean,
            street=street,
            street_occurrence=occurrence,
            frame_id=final_frame_id,
            previous_frame_id=previous_frame_id,
            signature=signature,
            previous_signature=previous_signature,
            validation_ok=True,
            validation_errors=[],
            validation_warnings=validation_warnings,
        )
        return decision, clear_to_save
