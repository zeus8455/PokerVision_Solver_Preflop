# Version history

## V2.1.0
Snapshot Solver_Preflop runtime source dry-run ON:
- sets V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = True in snapshot only
- keeps V20_SOLVER_PREFLOP_DRY_RUN_ONLY = True
- adds V2.1 compatibility adapter from Solver_Preflop bridge action_decision to legacy V06 Action_Decision_JSON shape
- runtime plan still uses existing Action_Runtime_Plan_JSON builder and guards
- real C:\PokerVisionFinalVersionNoSolver is not touched
- adds a runtime check proving Solver_Preflop bridge action_decision can feed Action_Runtime_Plan_JSON in snapshot dry-run mode

## V2.0.0
Snapshot-only runtime source switch scaffold.

## V1.9.0
Snapshot cycle bridge smoke.

## V1.8.0
Snapshot-only main startup smoke.

## V1.7.0
Solver_Preflop bridge diagnostic publication toggle.

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
