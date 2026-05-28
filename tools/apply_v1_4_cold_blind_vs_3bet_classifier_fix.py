from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPOT_CLASSIFIER = ROOT / "solver_preflop" / "spot_classifier.py"


OLD_BLOCK = """        if _is_close(hero_commitment, 0.0):
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
"""

NEW_BLOCK = """        if (
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
"""


def main() -> int:
    text = SPOT_CLASSIFIER.read_text(encoding="utf-8")

    if "blind-only commitment" in text:
        print({
            "status": "already_patched",
            "file": str(SPOT_CLASSIFIER),
            "cold_blind_fix_present": True,
        })
        return 0

    if OLD_BLOCK not in text:
        raise RuntimeError("V1.4 cold blind classifier anchor not found in solver_preflop/spot_classifier.py")

    text = text.replace(OLD_BLOCK, NEW_BLOCK, 1)
    SPOT_CLASSIFIER.write_text(text, encoding="utf-8")

    print({
        "status": "patched",
        "file": str(SPOT_CLASSIFIER),
        "cold_blind_fix_present": True,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
