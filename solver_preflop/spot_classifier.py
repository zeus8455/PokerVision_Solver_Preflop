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


def _raise_delta_context(raise_levels: list[float]) -> tuple[float | None, float | None, bool | None]:
    """Return previous_level, min_full_raise_delta, is_full_raise for all-in at max level.

    Uses frame-local commitment levels only. This is a conservative diagnostic,
    not a complete betting-ledger replacement.
    """
    if not raise_levels:
        return None, None, None

    current = raise_levels[-1]

    if len(raise_levels) == 1:
        previous_level = 1.0
        min_full_raise_delta = max(1.0, raise_levels[0] - 1.0)
    else:
        previous_level = raise_levels[-2]
        min_full_raise_delta = raise_levels[-2] - (raise_levels[-3] if len(raise_levels) >= 3 else 1.0)

    raise_delta = current - previous_level
    is_full_raise = raise_delta >= min_full_raise_delta - 1e-9
    return previous_level, min_full_raise_delta, is_full_raise


def _classify_all_in_spot(
    *,
    frame: NormalizedPreflopFrame,
    active_players: list[NormalizedPlayer],
    common: dict,
    raise_levels: list[float],
) -> PreflopSpot:
    hero = frame.hero_player
    all_in_players = common["all_in_players"]
    max_commitment = common["max_commitment_bb"]
    hero_commitment = common["hero_commitment_bb"]

    all_in_at_max = [
        p for p in active_players
        if p.all_in and _is_close(p.committed_bb, max_commitment)
    ]
    all_in_actor = all_in_at_max[0] if all_in_at_max else next((p for p in active_players if p.all_in), None)

    previous_level, min_full_raise_delta, is_full_raise = _raise_delta_context(raise_levels)
    all_in_raise_delta = None if previous_level is None else max_commitment - previous_level
    reopens_action = bool(is_full_raise) if is_full_raise is not None else None

    all_in_diag = {
        "all_in_amount_bb": max_commitment if all_in_actor is not None else None,
        "all_in_actor_pos": all_in_actor.position if all_in_actor is not None else None,
        "all_in_previous_level_bb": previous_level,
        "all_in_raise_delta_bb": all_in_raise_delta,
        "all_in_min_full_raise_delta_bb": min_full_raise_delta,
        "all_in_is_full_raise": is_full_raise,
        "all_in_reopens_action": reopens_action,
    }

    if hero.all_in:
        return PreflopSpot(
            node_type="hero_already_allin_no_decision",
            notes=["Hero is already all-in; Solver must not request another click."],
            **common,
            **all_in_diag,
        )

    if max_commitment <= 1.0:
        return PreflopSpot(
            node_type="facing_short_allin",
            notes=["All-in amount is at or below blind level; guarded fallback until short all-in ranges exist."],
            **common,
            **all_in_diag,
        )

    if len(raise_levels) == 1:
        opener_pos = all_in_actor.position if all_in_actor is not None else None
        node = "blind_vs_open_jam" if hero.position in {"SB", "BB"} and hero_commitment > 0 else "facing_open_jam"
        return PreflopSpot(
            node_type=node,
            opener_pos=opener_pos,
            last_aggressor_pos=opener_pos,
            facing_raise_size_bb=max_commitment,
            notes=["Open-jam all-in node is classified, but all-in ranges are not wired in V0.6."],
            **common,
            **all_in_diag,
        )

    if len(raise_levels) >= 2:
        first_raise = raise_levels[0]
        second_raise = raise_levels[1]
        third_raise = raise_levels[2] if len(raise_levels) >= 3 else None

        opener_pos = _first_position(_positions_with_commitment(active_players, first_raise))
        three_bettor_pos = _first_position(_positions_with_commitment(active_players, second_raise))
        four_bettor_pos = _first_position(_positions_with_commitment(active_players, third_raise)) if third_raise is not None else None

        if _is_close(hero_commitment, first_raise) and hero_commitment < max_commitment:
            node = "opener_vs_3bet_jam" if is_full_raise else "opener_vs_incomplete_3bet_allin"
            return PreflopSpot(
                node_type=node,
                opener_pos=hero.position,
                three_bettor_pos=all_in_actor.position if all_in_actor is not None else three_bettor_pos,
                last_aggressor_pos=all_in_actor.position if all_in_actor is not None else three_bettor_pos,
                previous_raise_size_bb=first_raise,
                facing_raise_size_bb=max_commitment,
                notes=["Opener-vs-all-in 3bet node classified; guarded fallback until all-in ranges exist."],
                **common,
                **all_in_diag,
            )

        if _is_close(hero_commitment, second_raise) and hero_commitment < max_commitment:
            node = "threebettor_vs_4bet_jam" if is_full_raise else "threebettor_vs_incomplete_4bet_allin"
            return PreflopSpot(
                node_type=node,
                opener_pos=opener_pos,
                three_bettor_pos=hero.position,
                four_bettor_pos=all_in_actor.position if all_in_actor is not None else four_bettor_pos,
                last_aggressor_pos=all_in_actor.position if all_in_actor is not None else four_bettor_pos,
                previous_raise_size_bb=second_raise,
                facing_raise_size_bb=max_commitment,
                notes=["Threebettor-vs-all-in 4bet node classified; guarded fallback until all-in ranges exist."],
                **common,
                **all_in_diag,
            )

        if _is_close(hero_commitment, 0.0):
            return PreflopSpot(
                node_type="cold_vs_allin_3bet_or_higher",
                opener_pos=opener_pos,
                three_bettor_pos=three_bettor_pos,
                four_bettor_pos=four_bettor_pos,
                last_aggressor_pos=all_in_actor.position if all_in_actor is not None else None,
                facing_raise_size_bb=max_commitment,
                notes=["Cold all-in node classified; guarded fallback until cold all-in ranges exist."],
                **common,
                **all_in_diag,
            )

    return PreflopSpot(
        node_type="facing_allin_or_allin_present",
        notes=["V0.6 could not resolve a more specific all-in node; guarded fallback."],
        **common,
        **all_in_diag,
    )


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
        return _classify_all_in_spot(
            frame=frame,
            active_players=active_players,
            common=common,
            raise_levels=raise_levels,
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
            notes=["No raise exists, but V0.6 cannot classify this no-raise state."],
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
            notes=["Single raise exists, but V0.6 cannot classify hero relationship to it."],
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

        if (
            _is_close(hero_commitment, 0.0)
            or (hero.position == "SB" and hero_commitment < max_commitment and hero_commitment <= 0.5 + 1e-9)
            or (hero.position == "BB" and hero_commitment < max_commitment and hero_commitment <= 1.0 + 1e-9)
        ):
            return PreflopSpot(
                node_type="cold_vs_3bet_or_higher",
                opener_pos=opener_pos,
                three_bettor_pos=three_bettor_pos,
                four_bettor_pos=four_bettor_pos,
                last_aggressor_pos=last_aggressor_pos,
                facing_raise_size_bb=max_commitment,
                notes=["Hero cold-faces multiple raise levels from no voluntary preflop action or blind-only commitment."],
                **common,
            )

        return PreflopSpot(
            node_type="multi_raise_unknown",
            opener_pos=opener_pos,
            three_bettor_pos=three_bettor_pos,
            four_bettor_pos=four_bettor_pos,
            last_aggressor_pos=last_aggressor_pos,
            facing_raise_size_bb=max_commitment,
            notes=["Multiple raise levels exist, but V0.6 cannot classify hero relationship to them."],
            **common,
        )

    return PreflopSpot(
        node_type="unknown_preflop_spot",
        notes=["V0.6 terminal fallback node."],
        **common,
    )
