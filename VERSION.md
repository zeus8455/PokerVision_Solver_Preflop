# Version history

## V0.4.0
Ranges foundation:
- adds JSON hero preflop ranges
- adds range_parser.py for 169 hand-class expansion
- adds range_loader.py
- adds range_engine.py
- decision engine now uses range lookup for:
  - unopened/RFI
  - SB first-in
  - BB vs SB limp
  - BB option vs non-blind limpers
  - iso vs limp
- keeps unsupported/all-in nodes guarded by safe fallback

## V0.3.0
Preflop spot classifier expansion:
- classifies SB first-in spot
- classifies facing_open / blind_vs_open / limper_vs_iso
- classifies opener_vs_small_3bet / opener_vs_normal_3bet / opener_vs_large_3bet
- classifies threebettor_vs_small_4bet / normal / large
- exposes commitment_by_pos, raise_levels, previous_raise_size, facing_raise_size, sizing_category in debug
- preserves safe fallback for all-in and unsupported nodes

## V0.2.0
Clear_JSON adapter hardening and synthetic preflop cases:
- chips:false is treated as 0bb committed
- absent all_in is treated as False
- all_in:true requires numeric chips
- folded players remain parsed but inactive
- sitout players, if present, are excluded from active hand state
- already clicked Clear_JSON is rejected as solver input
- hero validation tightened
- synthetic tests added for Clear_JSON edge cases

## V0.1.1
Removed Python cache artifacts from Git.

## V0.1.0
Initial skeleton.
