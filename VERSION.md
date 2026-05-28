# Version history

## V0.6.0
All-in guard logic:
- adds specific preflop all-in node classification
- distinguishes open jam, blind vs open jam, opener vs 3bet jam, threebettor vs 4bet jam
- detects incomplete all-in raise candidates from frame-local commitment levels
- keeps all all-in nodes in safe fallback until dedicated all-in ranges are added
- exposes all-in diagnostics in SolverDecision debug
- updates all-in tests to validate guarded behavior

## V0.5.0
Defensive ranges:
- extends hero_preflop_ranges.json with VS_OPEN, VS_OPEN_CALLERS, OPENER_VS_3BET, THREEBETTER_VS_4BET, LIMPER_VS_ISO and COLD_4BET from the old Solver ranges.py hero profile
- range_engine now resolves:
  - facing_open
  - blind_vs_open
  - limper_vs_iso
  - opener_vs_small_3bet / normal / large
  - threebettor_vs_small_4bet / normal / large
- adds small_3bet override: opener facing <=2.1x 3bet defends by call if chart would otherwise fold
- updates legacy classifier tests so they validate classification, not old placeholder actions

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
