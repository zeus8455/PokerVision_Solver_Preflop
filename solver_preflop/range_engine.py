from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import PreflopSpot
from .range_loader import load_hero_ranges
from .range_parser import hand_in_range


ACTION_PRIORITY = (
    "5bet_jam",
    "4bet",
    "3bet",
    "iso_raise",
    "open_raise",
    "raise",
    "call",
    "limp",
    "check",
    "fold",
)


@dataclass(slots=True, frozen=True)
class RangeDecision:
    action: str
    source: str
    matched_range: str | None = None
    fallback_used: bool = False
    notes: list[str] = field(default_factory=list)


def _pick_from_action_map(hand_class: str, action_map: dict[str, str], *, default_action: str, source: str) -> RangeDecision:
    normalized = {str(action): str(expr or "") for action, expr in action_map.items()}
    for action in ACTION_PRIORITY:
        expr = normalized.get(action)
        if expr and hand_in_range(hand_class, expr):
            return RangeDecision(
                action=action,
                source=source,
                matched_range=expr,
                fallback_used=False,
            )
    return RangeDecision(
        action=default_action,
        source=source,
        matched_range=None,
        fallback_used=True,
        notes=[f"Hand {hand_class} not found in {source}; default={default_action}."],
    )


def _placeholder_call_for_supported_future_node(node: str) -> RangeDecision | None:
    """Preserve V0.3 behaviour for classified nodes whose ranges are not wired yet.

    V0.4 adds real ranges only for RFI/SB/limp/iso branches. Defensive raise
    branches are classified, but their range tables arrive in later versions.
    They must remain non-crashing and non-regressive for existing V0.3 tests.
    """
    if node in {"facing_open", "blind_vs_open", "limper_vs_iso"}:
        return RangeDecision(
            action="call",
            source=f"placeholder.{node}",
            fallback_used=True,
            notes=[f"{node} is classified, but range table is not wired in V0.4; preserving placeholder call."],
        )

    if node.startswith("opener_vs_") and "3bet" in node:
        return RangeDecision(
            action="call",
            source=f"placeholder.{node}",
            fallback_used=True,
            notes=[f"{node} is classified, but 3bet-defense ranges are not wired in V0.4; preserving placeholder call."],
        )

    if node.startswith("threebettor_vs_") and "4bet" in node:
        return RangeDecision(
            action="call",
            source=f"placeholder.{node}",
            fallback_used=True,
            notes=[f"{node} is classified, but 4bet-defense ranges are not wired in V0.4; preserving placeholder call."],
        )

    if node.startswith("fourbettor_vs_") and "5bet" in node:
        return RangeDecision(
            action="call",
            source=f"placeholder.{node}",
            fallback_used=True,
            notes=[f"{node} is classified, but 5bet-defense ranges are not wired in V0.4; preserving placeholder call."],
        )

    return None


def decide_preflop_action_from_ranges(
    *,
    hand_class: str,
    spot: PreflopSpot,
    range_data: dict[str, Any] | None = None,
) -> RangeDecision:
    data = range_data or load_hero_ranges()
    nodes = data.get("nodes") or {}
    defaults = data.get("defaults") or {}

    node = spot.node_type

    if node == "unopened":
        action_map = ((nodes.get("rfi") or {}).get(spot.hero_position) or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=str(defaults.get("unopened") or "fold"),
            source=f"rfi.{spot.hero_position}",
        )

    if node == "sb_first_in":
        action_map = ((nodes.get("sb_first_in") or {}).get("SB") or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=str(defaults.get("sb_first_in") or "fold"),
            source="sb_first_in.SB",
        )

    if node == "bb_vs_sb_limp":
        action_map = ((nodes.get("bb_vs_sb_limp") or {}).get("BB") or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=str(defaults.get("bb_vs_sb_limp") or "check"),
            source="bb_vs_sb_limp.BB",
        )

    if node.startswith("bb_option_vs_"):
        action_map = ((nodes.get("iso_raise") or {}).get("BB") or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=str(defaults.get("bb_option_vs_limp") or "check"),
            source="iso_raise.BB",
        )

    if node.startswith("iso_vs_"):
        action_map = ((nodes.get("iso_raise") or {}).get(spot.hero_position) or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=str(defaults.get("iso_vs_limp") or "fold"),
            source=f"iso_raise.{spot.hero_position}",
        )

    placeholder = _placeholder_call_for_supported_future_node(node)
    if placeholder is not None:
        return placeholder

    return RangeDecision(
        action="safe_fallback",
        source=f"unsupported.{node}",
        fallback_used=True,
        notes=[f"V0.4 range engine does not support node_type={node}."],
    )
