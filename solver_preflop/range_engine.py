from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import PreflopSpot
from .range_loader import load_hero_ranges
from .range_parser import hand_in_range


ACTION_PRIORITY = (
    "5bet_jam",
    "5bet",
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


ALL_IN_NODE_PREFIXES = (
    "facing_open_jam",
    "blind_vs_open_jam",
    "opener_vs_3bet_jam",
    "opener_vs_incomplete_3bet_allin",
    "threebettor_vs_4bet_jam",
    "threebettor_vs_incomplete_4bet_allin",
    "cold_vs_allin_3bet_or_higher",
    "facing_short_allin",
    "hero_already_allin_no_decision",
    "facing_allin_or_allin_present",
    "facing_allin_unknown_amount",
)


@dataclass(slots=True, frozen=True)
class RangeDecision:
    action: str
    source: str
    matched_range: str | None = None
    fallback_used: bool = False
    notes: list[str] = field(default_factory=list)


def _join_key(*parts: object) -> str:
    return "|".join(str(p) for p in parts)


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


def _lookup_action_map(node_maps: dict[str, Any], node_name: str, *key_parts: object) -> tuple[dict[str, str], str]:
    node = node_maps.get(node_name) or {}
    key = _join_key(*key_parts)
    action_map = node.get(key)
    if isinstance(action_map, dict):
        return {str(k): str(v or "") for k, v in action_map.items()}, f"{node_name}.{key}"
    return {}, f"{node_name}.{key}.missing"


def _best_fallback_by_hero(node_maps: dict[str, Any], node_name: str, hero_pos: str, preferred_second: str | None = None) -> tuple[dict[str, str], str]:
    node = node_maps.get(node_name) or {}
    candidates: list[tuple[int, str, dict[str, str]]] = []
    for key, value in node.items():
        parts = str(key).split("|")
        if not isinstance(value, dict):
            continue
        if len(parts) >= 2 and parts[0] == hero_pos:
            score = 0 if preferred_second is not None and len(parts) >= 2 and parts[1] == preferred_second else 10
            candidates.append((score, key, {str(k): str(v or "") for k, v in value.items()}))
        elif len(parts) >= 2 and parts[-1] == hero_pos:
            score = 20
            candidates.append((score, key, {str(k): str(v or "") for k, v in value.items()}))
    if not candidates:
        return {}, f"{node_name}.fallback_missing"
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, key, action_map = candidates[0]
    return action_map, f"{node_name}.fallback.{key}"


def _default_for(data: dict[str, Any], name: str, fallback: str) -> str:
    return str((data.get("defaults") or {}).get(name) or fallback)


def _is_all_in_node(node: str) -> bool:
    return node.startswith(ALL_IN_NODE_PREFIXES)


def decide_preflop_action_from_ranges(
    *,
    hand_class: str,
    spot: PreflopSpot,
    range_data: dict[str, Any] | None = None,
) -> RangeDecision:
    data = range_data or load_hero_ranges()
    nodes = data.get("nodes") or {}
    node = spot.node_type

    if _is_all_in_node(node):
        return RangeDecision(
            action="safe_fallback",
            source=f"allin_guard.{node}",
            fallback_used=True,
            notes=[
                f"{node} classified, but all-in decision ranges are not wired in V0.6.",
                "Safe fallback click sequence must be used.",
            ],
        )

    if node == "unopened":
        action_map = ((nodes.get("rfi") or {}).get(spot.hero_position) or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=_default_for(data, "unopened", "fold"),
            source=f"rfi.{spot.hero_position}",
        )

    if node == "sb_first_in":
        action_map = ((nodes.get("sb_first_in") or {}).get("SB") or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=_default_for(data, "sb_first_in", "fold"),
            source="sb_first_in.SB",
        )

    if node == "bb_vs_sb_limp":
        action_map = ((nodes.get("bb_vs_sb_limp") or {}).get("BB") or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=_default_for(data, "bb_vs_sb_limp", "check"),
            source="bb_vs_sb_limp.BB",
        )

    # V239_BB_UNOPENED_OPTION_DEFAULT_CHECK:
    # Logical BB no-raise/no-limper option. If this frame ever reaches an Active
    # cycle, the safe preflop action is a guarded check attempt, not unknown fallback.
    if node == "bb_unopened_option_no_raise":
        return RangeDecision(
            action=_default_for(data, "bb_unopened_option_no_raise", "check"),
            source="bb_unopened_option_no_raise.default",
            fallback_used=True,
            notes=["BB no-raise option classified; default guarded check."],
        )

    if node.startswith("bb_option_vs_"):
        action_map = ((nodes.get("iso_raise") or {}).get("BB") or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=_default_for(data, "bb_option_vs_limp", "check"),
            source="iso_raise.BB",
        )

    if node.startswith("iso_vs_"):
        action_map = ((nodes.get("iso_raise") or {}).get(spot.hero_position) or {})
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=_default_for(data, "iso_vs_limp", "fold"),
            source=f"iso_raise.{spot.hero_position}",
        )

    if node in {"facing_open", "blind_vs_open"}:
        if not spot.opener_pos:
            return RangeDecision(
                action="safe_fallback",
                source=f"vs_open.missing_opener.{spot.hero_position}",
                fallback_used=True,
                notes=["Cannot resolve facing_open without opener_pos."],
            )
        action_map, source = _lookup_action_map(nodes, "vs_open", spot.opener_pos, spot.hero_position)
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=_default_for(data, node, "fold"),
            source=source,
        )

    if node == "limper_vs_iso":
        if not spot.opener_pos:
            return RangeDecision(
                action="safe_fallback",
                source=f"limper_vs_iso.missing_iso_raiser.{spot.hero_position}",
                fallback_used=True,
                notes=["Cannot resolve limper_vs_iso without opener_pos/iso_raiser."],
            )
        action_map, source = _lookup_action_map(nodes, "limper_vs_iso", spot.hero_position, spot.opener_pos)
        if not action_map:
            action_map, source = _best_fallback_by_hero(nodes, "limper_vs_iso", spot.hero_position, spot.opener_pos)
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=_default_for(data, "limper_vs_iso", "fold"),
            source=source,
        )

    if node == "caller_vs_3bet_or_higher":
        return RangeDecision(
            action=_default_for(data, "caller_vs_3bet_or_higher", "fold"),
            source=f"caller_vs_3bet_or_higher.{spot.hero_position}",
            fallback_used=True,
            notes=["V2.43 caller-vs-3bet/squeeze classified; guarded default until caller-vs-squeeze ranges exist."],
        )

    if node.startswith("opener_vs_") and "3bet" in node:
        if not spot.three_bettor_pos:
            return RangeDecision(
                action="safe_fallback",
                source=f"opener_vs_3bet.missing_threebettor.{spot.hero_position}",
                fallback_used=True,
                notes=["Cannot resolve opener_vs_3bet without three_bettor_pos."],
            )
        action_map, source = _lookup_action_map(nodes, "opener_vs_3bet", spot.hero_position, spot.three_bettor_pos)
        if not action_map:
            action_map, source = _best_fallback_by_hero(nodes, "opener_vs_3bet", spot.hero_position, spot.three_bettor_pos)

        default_action = _default_for(data, "opener_vs_3bet", "fold")
        decision = _pick_from_action_map(hand_class, action_map, default_action=default_action, source=source)

        if node == "opener_vs_small_3bet" and decision.action == "fold":
            return RangeDecision(
                action=_default_for(data, "small_3bet_override", "call"),
                source=source + ".small_3bet_override",
                matched_range=decision.matched_range,
                fallback_used=True,
                notes=decision.notes + ["Small 3bet override: defend by call instead of default fold."],
            )
        return decision

    if node.startswith("threebettor_vs_") and "4bet" in node:
        if not spot.four_bettor_pos:
            return RangeDecision(
                action="safe_fallback",
                source=f"threebettor_vs_4bet.missing_fourbettor.{spot.hero_position}",
                fallback_used=True,
                notes=["Cannot resolve threebettor_vs_4bet without four_bettor_pos."],
            )
        action_map, source = _lookup_action_map(nodes, "threebettor_vs_4bet", spot.hero_position, spot.four_bettor_pos)
        if not action_map:
            action_map, source = _best_fallback_by_hero(nodes, "threebettor_vs_4bet", spot.hero_position, spot.four_bettor_pos)
        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=_default_for(data, "threebettor_vs_4bet", "fold"),
            source=source,
        )

    if node == "cold_vs_3bet_or_higher":
        if not spot.opener_pos or not spot.three_bettor_pos:
            return RangeDecision(
                action="safe_fallback",
                source=f"cold_4bet.missing_positions.{spot.hero_position}",
                fallback_used=True,
                notes=["Cannot resolve cold_vs_3bet_or_higher without opener_pos and three_bettor_pos."],
            )

        action_map, source = _lookup_action_map(
            nodes,
            "cold_4bet",
            spot.opener_pos,
            spot.three_bettor_pos,
            spot.hero_position,
        )
        if not action_map:
            return RangeDecision(
                action="safe_fallback",
                source=source,
                fallback_used=True,
                notes=[
                    "cold_vs_3bet_or_higher was classified, but no exact cold_4bet chart key exists.",
                    f"missing_key={spot.opener_pos}|{spot.three_bettor_pos}|{spot.hero_position}",
                ],
            )

        return _pick_from_action_map(
            hand_class,
            action_map,
            default_action=_default_for(data, "cold_vs_3bet_or_higher", "fold"),
            source=source,
        )

    if node.startswith("fourbettor_vs_") and "5bet" in node:
        return RangeDecision(
            action="safe_fallback",
            source=f"unsupported.{node}",
            fallback_used=True,
            notes=["V0.6 does not yet include 4bettor-vs-5bet non-jam ranges."],
        )

    return RangeDecision(
        action="safe_fallback",
        source=f"unsupported.{node}",
        fallback_used=True,
        notes=[f"V0.6 range engine does not support node_type={node}."],
    )
