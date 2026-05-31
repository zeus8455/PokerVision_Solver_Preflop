from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


SOLVER_NAME = "PokerVision_Solver_Preflop"
SOLVER_VERSION = "1.0.0"
SOLVER_CONTRACT_VERSION = "preflop_solver_response_v1"

POSITIONS_6MAX = ("UTG", "MP", "CO", "BTN", "SB", "BB")


@dataclass(slots=True, frozen=True)
class NormalizedPlayer:
    position: str
    hero: bool = False
    cards: list[str] = field(default_factory=list)
    stack_bb: float = 0.0
    committed_bb: float = 0.0
    folded: bool = False
    sitout: bool = False
    all_in: bool = False
    all_in_unknown_amount: bool = False
    active_in_hand: bool = True
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def can_act(self) -> bool:
        return self.active_in_hand and not self.all_in


@dataclass(slots=True, frozen=True)
class NormalizedPreflopFrame:
    frame_id: str
    street: str
    total_pot_bb: float
    hero_position: str
    hero_cards: list[str]
    players: dict[str, NormalizedPlayer]
    warnings: list[str] = field(default_factory=list)

    @property
    def hero_player(self) -> NormalizedPlayer:
        return self.players[self.hero_position]

    @property
    def active_players(self) -> list[NormalizedPlayer]:
        return [p for p in self.players.values() if p.active_in_hand]

    @property
    def active_positions(self) -> list[str]:
        return [p.position for p in self.active_players]


@dataclass(slots=True, frozen=True)
class PreflopSpot:
    node_type: str
    hero_position: str
    to_call_bb: float
    max_commitment_bb: float
    hero_commitment_bb: float = 0.0
    limpers: list[str] = field(default_factory=list)
    opener_pos: Optional[str] = None
    three_bettor_pos: Optional[str] = None
    four_bettor_pos: Optional[str] = None
    last_aggressor_pos: Optional[str] = None
    all_in_players: list[str] = field(default_factory=list)
    commitment_by_pos: dict[str, float] = field(default_factory=dict)
    raise_levels: list[float] = field(default_factory=list)
    previous_raise_size_bb: Optional[float] = None
    facing_raise_size_bb: Optional[float] = None
    sizing_ratio: Optional[float] = None
    sizing_category: Optional[str] = None

    all_in_amount_bb: Optional[float] = None
    all_in_actor_pos: Optional[str] = None
    all_in_previous_level_bb: Optional[float] = None
    all_in_raise_delta_bb: Optional[float] = None
    all_in_min_full_raise_delta_bb: Optional[float] = None
    all_in_is_full_raise: Optional[bool] = None
    all_in_reopens_action: Optional[bool] = None

    notes: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SolverDecision:
    status: str
    street: str
    frame_id: str
    hero_position: str
    hero_hand: list[str]
    hand_class: str
    node_type: str
    raw_action: str
    engine_action: str
    click_sequence: list[str]
    reason: str
    size_pct: Optional[float] = None
    amount_to_bb: Optional[float] = None
    decision_id: Optional[str] = None
    solver_fingerprint: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)

    @property
    def safe_fallback_used(self) -> bool:
        return self.status == "fallback" or self.raw_action == "safe_fallback" or self.engine_action == "safe_fallback"

    @property
    def source_frame_id(self) -> str:
        return self.frame_id

    def _decision_block(self) -> dict[str, Any]:
        return {
            "raw_action": self.raw_action,
            "engine_action": self.engine_action,
            "size_pct": self.size_pct,
            "amount_to_bb": self.amount_to_bb,
            "click_sequence": list(self.click_sequence),
            "reason": self.reason,
        }

    def _runtime_hint_block(self) -> dict[str, Any]:
        return {
            "contract": "pokervision_action_runtime_hint_v1",
            "source": "solver_preflop",
            "source_frame_id": self.source_frame_id,
            "decision_id": self.decision_id,
            "solver_fingerprint": self.solver_fingerprint,
            "street": self.street,
            "engine_action": self.engine_action,
            "raw_action": self.raw_action,
            "size_pct": self.size_pct,
            "amount_to_bb": self.amount_to_bb,
            "click_sequence": list(self.click_sequence),
            "target_buttons": list(self.click_sequence),
            "safe_fallback_used": self.safe_fallback_used,
            "runtime_action_allowed": bool(self.click_sequence),
            "notes": [
                "PokerVision runtime must still apply its own guards: Active, slot ROI, no-repeat, dry-run/real-click flags, button availability.",
            ],
        }

    def _safety_block(self) -> dict[str, Any]:
        return {
            "safe_fallback_used": self.safe_fallback_used,
            "fallback_click_sequence": ["Check", "Check/fold", "FOLD"] if self.safe_fallback_used else None,
            "real_click_allowed_by_solver": bool(self.click_sequence),
            "requires_pokervision_runtime_guards": True,
            "must_not_bypass_click_guards": True,
        }

    def _input_summary_block(self) -> dict[str, Any]:
        return {
            "source_frame_id": self.source_frame_id,
            "street": self.street,
            "hero_position": self.hero_position,
            "hero_hand": list(self.hero_hand),
            "hand_class": self.hand_class,
            "node_type": self.node_type,
            "to_call_bb": self.debug.get("to_call_bb"),
            "max_commitment_bb": self.debug.get("max_commitment_bb"),
            "hero_commitment_bb": self.debug.get("hero_commitment_bb"),
            "commitment_by_pos": self.debug.get("commitment_by_pos"),
            "active_limpers": self.debug.get("limpers"),
            "all_in_players": self.debug.get("all_in_players"),
        }

    def _spot_debug_block(self) -> dict[str, Any]:
        keys = [
            "to_call_bb",
            "max_commitment_bb",
            "hero_commitment_bb",
            "commitment_by_pos",
            "raise_levels",
            "limpers",
            "all_in_players",
            "all_in_amount_bb",
            "all_in_actor_pos",
            "all_in_previous_level_bb",
            "all_in_raise_delta_bb",
            "all_in_min_full_raise_delta_bb",
            "all_in_is_full_raise",
            "all_in_reopens_action",
            "opener_pos",
            "three_bettor_pos",
            "four_bettor_pos",
            "last_aggressor_pos",
            "previous_raise_size_bb",
            "facing_raise_size_bb",
            "sizing_ratio",
            "sizing_category",
            "range_source",
            "matched_range",
            "range_fallback_used",
        ]
        return {key: self.debug.get(key) for key in keys}

    def to_json_dict(self) -> dict[str, Any]:
        decision_block = self._decision_block()
        return {
            "solver": {
                "name": SOLVER_NAME,
                "version": SOLVER_VERSION,
                "contract": SOLVER_CONTRACT_VERSION,
                "street": self.street,
                "status": self.status,
            },
            "source": {
                "frame_id": self.frame_id,
                "source_frame_id": self.source_frame_id,
                "input_type": "Clear_JSON",
                "solver_source": "PokerVision_Solver_Preflop",
            },
            "hero": {
                "position": self.hero_position,
                "hand": list(self.hero_hand),
                "hand_class": self.hand_class,
            },
            "spot": {
                "node_type": self.node_type,
            },
            "decision": decision_block,
            "action_runtime_hint": self._runtime_hint_block(),
            "identity": {
                "decision_id": self.decision_id,
                "solver_decision_id": self.decision_id,
                "solver_fingerprint": self.solver_fingerprint,
                "source_frame_id": self.source_frame_id,
            },
            "safety": self._safety_block(),
            "input_summary": self._input_summary_block(),
            "spot_debug": self._spot_debug_block(),
            "warnings": list(self.warnings),
            "debug": dict(self.debug),
        }

    def to_action_decision_dict(self) -> dict[str, Any]:
        """Compact bridge payload for future PokerVision Action_Decision_JSON wiring."""
        return {
            "schema": "pokervision_solver_action_decision_v1",
            "source": "PokerVision_Solver_Preflop",
            "source_frame_id": self.source_frame_id,
            "street": self.street,
            "decision_id": self.decision_id,
            "solver_fingerprint": self.solver_fingerprint,
            "hero_position": self.hero_position,
            "hero_hand": list(self.hero_hand),
            "hand_class": self.hand_class,
            "node_type": self.node_type,
            "raw_action": self.raw_action,
            "engine_action": self.engine_action,
            "size_pct": self.size_pct,
            "amount_to_bb": self.amount_to_bb,
            "click_sequence": list(self.click_sequence),
            "safe_fallback_used": self.safe_fallback_used,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "debug": dict(self.debug),
        }
