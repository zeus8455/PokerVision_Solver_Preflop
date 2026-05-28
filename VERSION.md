# Version history

## V2.3.0
Snapshot Solver_Preflop runtime plan publication check:
- adds tools/run_v2_3_snapshot_runtime_publication_check.py
- verifies Solver-sourced Action_Runtime_Plan_JSON can be published to files
- runs all snapshot Pending preflop Clear_JSON cases through:
  Pending Clear_JSON -> Solver_Preflop bridge -> Solver action_decision
  -> V2.1 legacy adapter -> Action_Runtime_Plan_JSON file publication
- verifies saved runtime plan JSON files exist and match the in-memory contract
- keeps dry_run=True and real_click_enabled=False
- does not execute full live UI, screen capture, YOLO, or touch C:\PokerVisionFinalVersionNoSolver
- adds test coverage for the publication path

## V2.2.0
Snapshot Solver_Preflop runtime source multi-case check:
- adds tools/run_v2_2_snapshot_solver_source_multicase_check.py
- runs every snapshot Pending preflop Clear_JSON through:
  Pending Clear_JSON -> Solver_Preflop bridge -> Solver action_decision
  -> V2.1 legacy-compatible Action_Decision_JSON adapter
  -> Action_Runtime_Plan_JSON
- verifies selected_source=Solver_Preflop_Bridge for all cases
- verifies runtime plans for fold/check cases are valid and dry-run only
- verifies no full live UI, screen capture, YOLO, or real project mutation
- adds test coverage for the multi-case runtime source path

## V2.1.0
Snapshot Solver_Preflop runtime source dry-run ON.

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
