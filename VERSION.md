# Version history

## V1.8.0
Snapshot-only main startup smoke:
- adds tools/run_snapshot_main_startup_smoke.py
- runs snapshot PokerVision main.py with --startup-audit-only
- never touches C:\PokerVisionFinalVersionNoSolver
- verifies snapshot display_analysis_cycle.py contains Solver_Preflop dry-run bridge wiring
- verifies snapshot bridge module can locate C:\PokerVision_Solver_Preflop through env/default root
- verifies startup audit exits before live UI launch
- adds test coverage for snapshot-only main smoke

## V1.7.0
Solver_Preflop bridge diagnostic publication toggle:
- adds a display_analysis_cycle.py toggle:
  V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES = False
- wires pending-preview Solver_Preflop bridge call to that toggle
- default behavior stays safe: no diagnostic files are published
- adds tools/run_solver_preflop_bridge_publication_check.py
- verifies direct bridge publication writes Solver_Preflop_Bridge_JSON/table_xx/*.solver_preflop_bridge_preview.json
- adds static and runtime tests for the publication toggle

## V1.6.0
Display-cycle bridge embedding check.

## V1.5.0
Cold-vs-3bet range support.

## V1.4.0
Cold blind vs 3bet classifier fix.

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
