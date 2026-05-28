from __future__ import annotations

from .contracts import NormalizedPlayer, NormalizedPreflopFrame, POSITIONS_6MAX, PreflopSpot


def _is_close(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) < 1e-9


def _positions_with_commitment(players: list[NormalizedPlayer], amount: float) -> list[str]:
    return [
        p.position
        for p in players
        if _is_close(p.committed_bb, amount)
    ]


def _first_position(positions: list[str]) -> str | None:
    if not positions:
        return None
    return sorted(positions, key=lambda p: POSITIONS_6MAX.index(p))[0]


def _size_category(prefix: str, previous_size: float | None, facing_size: float | None) -> tuple[str | None, float | None]:
    if previous_size is None or facing_size is None or previous_size <= 0:
        return None, None
    ratio = float(facing_size) / float(previous_size)
    if ratio <= 2.1:
        return f"small_{prefix}", ratio
    if ratio <= 3.2:
        return f"normal_{prefix}", ratio
    return f"large_{prefix}", ratio


def classify_preflop_spot(frame: NormalizedPreflopFrame) -> PreflopSpot:
    active_players = frame.active_players
    hero = frame.hero_player

    commitment_by_pos = {p.position: p.committed_bb for p in frame.players.values()}
    max_commitment = max((p.committed_bb for p in active_players), default=0.0)
    hero_commitment = hero.committed_bb
    to_call = max(0.0, max_commitment - hero_commitment)
    all_in_players = [p.position for p in active_players if p.all_in]
    raise_levels = sorted({p.committed_bb for p in active_players if p.committed_bb > 1.0})
    has_raise = bool(raise_levels)

    limpers = [
        p.position
        for p in active_players
        if p.position not in ("SB", "BB") and _is_close(p.committed_bb, 1.0)
    ]

    common = {
        "hero_position": frame.hero_position,
        "to_call_bb": to_call,
        "max_commitment_bb": max_commitment,
        "hero_commitment_bb": hero_commitment,
        "limpers": limpers,
        "all_in_players": all_in_players,
        "commitment_by_pos": commitment_by_pos,
        "raise_levels": raise_levels,
    }

    if all_in_players:
        return PreflopSpot(
            node_type="facing_allin_or_allin_present",
            notes=["V0.4 classifies all-in only as a guarded node."],
            **common,
        )

    if not has_raise:
        sb = frame.players.get("SB")
        if (
            hero.position == "BB"
            and sb is not None
            and sb.active_in_hand
            and _is_close(sb.committed_bb, 1.0)
            and not limpers
            and _is_close(to_call, 0.0)
        ):
            return PreflopSpot(
                node_type="bb_vs_sb_limp",
                limpers=["SB"],
                notes=["Hero has logical preflop check option vs SB limp."],
                **{k: v for k, v in common.items() if k != "limpers"},
            )

        if hero.position == "BB" and limpers and _is_close(to_call, 0.0):
            return PreflopSpot(
                node_type=f"bb_option_vs_{len(limpers)}_limper" if len(limpers) == 1 else "bb_option_vs_2plus_limpers",
                notes=["Hero has logical preflop check option."],
                **common,
            )

        if hero.position == "SB" and not limpers and _is_close(hero_commitment, 0.5) and _is_close(max_commitment, 1.0):
            return PreflopSpot(
                node_type="sb_first_in",
                notes=["Hero SB acts first-in against BB blind."],
                **common,
            )

        if limpers and _is_close(hero_commitment, 0.0):
            return PreflopSpot(
                node_type=f"iso_vs_{len(limpers)}_limper" if len(limpers) == 1 else "iso_vs_2plus_limpers",
                **common,
            )

        if max_commitment <= 1.0 and not limpers and _is_close(hero_commitment, 0.0):
            return PreflopSpot(
                node_type="unopened",
                **common,
            )

        return PreflopSpot(
            node_type="unknown_no_raise_preflop_spot",
            notes=["No raise exists, but V0.4 cannot classify this no-raise state."],
            **common,
        )

    if len(raise_levels) == 1:
        open_size = raise_levels[0]
        aggressor_positions = _positions_with_commitment(active_players, open_size)
        opener_pos = _first_position([p for p in aggressor_positions if p != hero.position]) or _first_position(aggressor_positions)

        if _is_close(hero_commitment, 0.0):
            return PreflopSpot(
                node_type="facing_open",
                opener_pos=opener_pos,
                last_aggressor_pos=opener_pos,
                facing_raise_size_bb=open_size,
                **common,
            )

        if hero.position in ("SB", "BB") and hero_commitment < open_size:
            return PreflopSpot(
                node_type="blind_vs_open",
                opener_pos=opener_pos,
                last_aggressor_pos=opener_pos,
                facing_raise_size_bb=open_size,
                **common,
            )

        if _is_close(hero_commitment, 1.0) and hero.position not in ("SB", "BB") and hero_commitment < open_size:
            return PreflopSpot(
                node_type="limper_vs_iso",
                opener_pos=opener_pos,
                last_aggressor_pos=opener_pos,
                facing_raise_size_bb=open_size,
                **common,
            )

        if _is_close(hero_commitment, open_size) and _is_close(to_call, 0.0):
            return PreflopSpot(
                node_type="hero_is_current_aggressor_no_decision",
                opener_pos=hero.position,
                last_aggressor_pos=hero.position,
                facing_raise_size_bb=open_size,
                notes=["Hero appears to be current aggressor; active decision is not clear from frame-only state."],
                **common,
            )

        return PreflopSpot(
            node_type="facing_single_raise_unknown",
            opener_pos=opener_pos,
            last_aggressor_pos=opener_pos,
            facing_raise_size_bb=open_size,
            notes=["Single raise exists, but V0.4 cannot classify hero relationship to it."],
            **common,
        )

    if len(raise_levels) >= 2:
        first_raise = raise_levels[0]
        second_raise = raise_levels[1]
        third_raise = raise_levels[2] if len(raise_levels) >= 3 else None
        fourth_raise = raise_levels[3] if len(raise_levels) >= 4 else None

        opener_pos = _first_position(_positions_with_commitment(active_players, first_raise))
        three_bettor_pos = _first_position(_positions_with_commitment(active_players, second_raise))
        four_bettor_pos = _first_position(_positions_with_commitment(active_players, third_raise)) if third_raise is not None else None
        last_aggressor_pos = _first_position(_positions_with_commitment(active_players, max_commitment))

        if _is_close(hero_commitment, first_raise) and hero_commitment < max_commitment:
            category, ratio = _size_category("3bet", first_raise, second_raise)
            return PreflopSpot(
                node_type=f"opener_vs_{category}" if category else "opener_vs_3bet",
                opener_pos=hero.position,
                three_bettor_pos=three_bettor_pos,
                last_aggressor_pos=three_bettor_pos,
                previous_raise_size_bb=first_raise,
                facing_raise_size_bb=second_raise,
                sizing_ratio=ratio,
                sizing_category=category,
                **common,
            )

        if _is_close(hero_commitment, second_raise) and third_raise is not None and hero_commitment < max_commitment:
            category, ratio = _size_category("4bet", second_raise, third_raise)
            return PreflopSpot(
                node_type=f"threebettor_vs_{category}" if category else "threebettor_vs_4bet",
                opener_pos=opener_pos,
                three_bettor_pos=hero.position,
                four_bettor_pos=four_bettor_pos,
                last_aggressor_pos=four_bettor_pos,
                previous_raise_size_bb=second_raise,
                facing_raise_size_bb=third_raise,
                sizing_ratio=ratio,
                sizing_category=category,
                **common,
            )

        if _is_close(hero_commitment, third_raise or -1.0) and fourth_raise is not None and hero_commitment < max_commitment:
            category, ratio = _size_category("5bet", third_raise, fourth_raise)
            return PreflopSpot(
                node_type=f"fourbettor_vs_{category}" if category else "fourbettor_vs_5bet",
                opener_pos=opener_pos,
                three_bettor_pos=three_bettor_pos,
                four_bettor_pos=hero.position,
                last_aggressor_pos=last_aggressor_pos,
                previous_raise_size_bb=third_raise,
                facing_raise_size_bb=fourth_raise,
                sizing_ratio=ratio,
                sizing_category=category,
                **common,
            )

        if _is_close(hero_commitment, 0.0):
            return PreflopSpot(
                node_type="cold_vs_3bet_or_higher",
                opener_pos=opener_pos,
                three_bettor_pos=three_bettor_pos,
                four_bettor_pos=four_bettor_pos,
                last_aggressor_pos=last_aggressor_pos,
                facing_raise_size_bb=max_commitment,
                notes=["Hero has no commitment and faces multiple raise levels."],
                **common,
            )

        return PreflopSpot(
            node_type="multi_raise_unknown",
            opener_pos=opener_pos,
            three_bettor_pos=three_bettor_pos,
            four_bettor_pos=four_bettor_pos,
            last_aggressor_pos=last_aggressor_pos,
            facing_raise_size_bb=max_commitment,
            notes=["Multiple raise levels exist, but V0.4 cannot classify hero relationship to them."],
            **common,
        )

    return PreflopSpot(
        node_type="unknown_preflop_spot",
        notes=["V0.4 terminal fallback node."],
        **common,
    )
