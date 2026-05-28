from __future__ import annotations

from .contracts import NormalizedPreflopFrame, PreflopSpot


BLIND_COMMITMENTS = {"SB": 0.5, "BB": 1.0}


def classify_preflop_spot(frame: NormalizedPreflopFrame) -> PreflopSpot:
    active_players = [p for p in frame.players.values() if p.active_in_hand]
    hero = frame.hero_player

    max_commitment = max((p.committed_bb for p in active_players), default=0.0)
    to_call = max(0.0, max_commitment - hero.committed_bb)
    all_in_players = [p.position for p in active_players if p.all_in]

    # Limpers are active non-blind players who committed exactly BB and no raise exists.
    has_raise = max_commitment > 1.0
    limpers = [
        p.position
        for p in active_players
        if p.position not in ("SB", "BB") and abs(p.committed_bb - 1.0) < 1e-9
    ]

    notes: list[str] = []

    if all_in_players:
        return PreflopSpot(
            node_type="facing_allin_or_allin_present",
            hero_position=frame.hero_position,
            to_call_bb=to_call,
            max_commitment_bb=max_commitment,
            limpers=limpers,
            all_in_players=all_in_players,
            notes=["V0.1 classifies all-in only as a guarded node."],
        )

    if hero.position == "BB" and limpers and not has_raise and abs(to_call) < 1e-9:
        return PreflopSpot(
            node_type=f"bb_option_vs_{len(limpers)}_limper" if len(limpers) == 1 else "bb_option_vs_2plus_limpers",
            hero_position=frame.hero_position,
            to_call_bb=0.0,
            max_commitment_bb=max_commitment,
            limpers=limpers,
            all_in_players=[],
            notes=["Hero has logical preflop check option."],
        )

    if max_commitment <= 1.0 and not limpers and hero.committed_bb == 0:
        return PreflopSpot(
            node_type="unopened",
            hero_position=frame.hero_position,
            to_call_bb=0.0,
            max_commitment_bb=max_commitment,
            limpers=[],
            all_in_players=[],
        )

    if limpers and hero.committed_bb == 0 and not has_raise:
        return PreflopSpot(
            node_type=f"iso_vs_{len(limpers)}_limper" if len(limpers) == 1 else "iso_vs_2plus_limpers",
            hero_position=frame.hero_position,
            to_call_bb=max_commitment,
            max_commitment_bb=max_commitment,
            limpers=limpers,
            all_in_players=[],
        )

    if has_raise:
        raisers = [p for p in active_players if abs(p.committed_bb - max_commitment) < 1e-9 and p.position != hero.position]
        opener_pos = raisers[0].position if raisers else None
        return PreflopSpot(
            node_type="facing_open_or_raise",
            hero_position=frame.hero_position,
            to_call_bb=to_call,
            max_commitment_bb=max_commitment,
            opener_pos=opener_pos,
            limpers=limpers,
            all_in_players=[],
            notes=["V0.1 has only coarse raise classification."],
        )

    return PreflopSpot(
        node_type="unknown_preflop_spot",
        hero_position=frame.hero_position,
        to_call_bb=to_call,
        max_commitment_bb=max_commitment,
        limpers=limpers,
        all_in_players=[],
        notes=["V0.1 fallback node."],
    )
