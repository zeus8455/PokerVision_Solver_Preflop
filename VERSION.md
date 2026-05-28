# Version history

## V1.5.0
Cold-vs-3bet range support:
- wires cold_vs_3bet_or_higher into hero_preflop_ranges.json nodes.cold_4bet
- uses exact key opener|threebettor|hero, e.g. UTG|CO|SB
- returns fold/call/4bet from the cold_4bet chart instead of safe_fallback when the spot is supported
- keeps missing opener/threebettor or missing chart key guarded
- table_01_hand_21_preflop now returns fold instead of safe_fallback

## V1.4.0
Cold blind vs 3bet classifier fix:
- fixes SB/BB cold-facing multi-raise spots
- SB with 0.5bb blind and BB with 1.0bb blind can now classify as cold_vs_3bet_or_higher
- table_01_hand_21_preflop now becomes cold_vs_3bet_or_higher instead of multi_raise_unknown
- keeps decision guarded as safe_fallback until cold 4bet/all-in ranges are intentionally wired

## V1.3.0
Snapshot Clear_JSON bridge check.

## V1.2.0
PokerVision dry-run preflop solver bridge preview.

## V1.1.0
Imported PokerVisionFinalVersionNoSolver source snapshot.

## V1.0.1
Ignored preintegration output files.

## V1.0.0
Pre-integration stabilization.

## V0.9.0
PokerVision integration bridge preview.

## V0.8.1
Ignored generated solver output files.

## V0.8.0
CLI / file-output tools.

## V0.7.0
Solver response contract hardening.

## V0.6.0
All-in guard logic.

## V0.5.0
Defensive ranges.

## V0.4.0
Ranges foundation.

## V0.3.0
Preflop spot classifier expansion.

## V0.2.0
Clear_JSON adapter hardening and synthetic preflop cases.

## V0.1.1
Removed Python cache artifacts from Git.

## V0.1.0
Initial skeleton.
