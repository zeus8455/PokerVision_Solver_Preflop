r"""
runtime/solver_stub.py

PokerVision Core V1.1 — temporary solver/engine decision stub.

TODO V1.2: replace this module with a real solver_bridge / engine client.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from config import (
    V11_SOLVER_STUB_DEFAULT_ACTION,
    V11_SOLVER_STUB_DEFAULT_SIZE_PCT,
    V11_SOLVER_STUB_ENABLED,
)
from logic.action_button_policy import normalize_size_pct, normalize_solver_action


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _make_decision_id(payload: Dict[str, Any], action: str, size_pct: Optional[int]) -> str:
    table_id = payload.get("table_id") or "unknown_table"
    hand_id = payload.get("hand_id") or "unknown_hand"
    frame_name = payload.get("frame_name") or "unknown_frame"
    action_event_id = payload.get("action_event_id") or payload.get("action_signature") or frame_name
    size = "none" if size_pct is None else str(size_pct)
    # Deterministic by action event: the same visible Active spot must not create
    # a new synthetic decision id on every live scan pass.
    return f"v12_stub_{table_id}_{hand_id}_{action_event_id}_{action}_{size}"


def build_solver_stub_decision(
    solver_payload: Dict[str, Any],
    *,
    json_path: str | None = None,
    action: object = None,
    size_pct: object = None,
) -> Dict[str, Any]:
    """Return a deterministic temporary decision in the future solver response format."""
    started_at = time.perf_counter()

    if not V11_SOLVER_STUB_ENABLED:
        return {
            "status": "skipped",
            "source": "V1.1 temporary solver stub",
            "decision_id": None,
            "table_id": solver_payload.get("table_id"),
            "hand_id": solver_payload.get("hand_id"),
            "frame_name": solver_payload.get("frame_name"),
            "action": None,
            "size_pct": None,
            "reason": "V1.1 solver stub is disabled by config.",
            "processing_time_ms": _elapsed_ms(started_at),
            "json_path": json_path,
        }

    selected_action = normalize_solver_action(action if action is not None else V11_SOLVER_STUB_DEFAULT_ACTION)
    selected_size = normalize_size_pct(size_pct if size_pct is not None else V11_SOLVER_STUB_DEFAULT_SIZE_PCT)

    if selected_action != "bet_raise":
        selected_size = None

    decision_id = _make_decision_id(solver_payload, selected_action, selected_size)

    return {
        "status": "stub",
        "source": "V1.1 temporary solver stub",
        "decision_id": decision_id,
        "table_id": solver_payload.get("table_id"),
        "hand_id": solver_payload.get("hand_id"),
        "frame_name": solver_payload.get("frame_name"),
        "action": selected_action,
        "size_pct": selected_size,
        "reason": "Temporary hardcoded decision until real solver integration.",
        "processing_time_ms": _elapsed_ms(started_at),
        "json_path": json_path,
    }
