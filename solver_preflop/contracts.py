from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


POSITIONS_6MAX = ("UTG", "MP", "CO", "BTN", "SB", "BB")


@dataclass(slots=True, frozen=True)
class NormalizedPlayer:
    position: str
    hero: bool = False
    cards: list[str] = field(default_factory=list)
    stack_bb: float = 0.0
    committed_bb: float = 0.0
    folded: bool = False
    all_in: bool = False
    active_in_hand: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


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


@dataclass(slots=True, frozen=True)
class PreflopSpot:
    node_type: str
    hero_position: str
    to_call_bb: float
    max_commitment_bb: float
    limpers: list[str] = field(default_factory=list)
    opener_pos: Optional[str] = None
    three_bettor_pos: Optional[str] = None
    four_bettor_pos: Optional[str] = None
    all_in_players: list[str] = field(default_factory=list)
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

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "solver": {
                "name": "PokerVision_Solver_Preflop",
                "version": "0.1.0",
                "street": self.street,
                "status": self.status,
            },
            "source": {
                "frame_id": self.frame_id,
                "input_type": "Clear_JSON",
            },
            "hero": {
                "position": self.hero_position,
                "hand": self.hero_hand,
                "hand_class": self.hand_class,
            },
            "spot": {
                "node_type": self.node_type,
            },
            "decision": {
                "raw_action": self.raw_action,
                "engine_action": self.engine_action,
                "size_pct": self.size_pct,
                "amount_to_bb": self.amount_to_bb,
                "click_sequence": self.click_sequence,
                "reason": self.reason,
            },
            "identity": {
                "decision_id": self.decision_id,
                "solver_fingerprint": self.solver_fingerprint,
            },
            "warnings": list(self.warnings),
            "debug": dict(self.debug),
        }
