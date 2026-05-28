from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RANGE_ENGINE = ROOT / "solver_preflop" / "range_engine.py"


ANCHOR = """    if node.startswith("fourbettor_vs_") and "5bet" in node:
        return RangeDecision(
            action="safe_fallback",
            source=f"unsupported.{node}",
            fallback_used=True,
            notes=["V0.6 does not yet include 4bettor-vs-5bet non-jam ranges."],
        )

"""

INSERT = """    if node == "cold_vs_3bet_or_higher":
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

""" + ANCHOR


def main() -> int:
    text = RANGE_ENGINE.read_text(encoding="utf-8")

    if 'if node == "cold_vs_3bet_or_higher":' in text:
        print({
            "status": "already_patched",
            "file": str(RANGE_ENGINE),
            "cold_4bet_support_present": True,
        })
        return 0

    if ANCHOR not in text:
        raise RuntimeError("V1.5 cold_4bet range_engine anchor not found.")

    text = text.replace(ANCHOR, INSERT, 1)
    RANGE_ENGINE.write_text(text, encoding="utf-8")

    print({
        "status": "patched",
        "file": str(RANGE_ENGINE),
        "cold_4bet_support_present": True,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
