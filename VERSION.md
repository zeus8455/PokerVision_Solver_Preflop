# Version history

## V2.5.0
Snapshot Solver_Preflop dry-run click-result publication check:
- adds tools/run_v2_5_snapshot_click_result_publication_check.py
- runs all snapshot Pending preflop Clear_JSON cases through:
  Pending Clear_JSON -> Solver_Preflop bridge -> V2.1 adapter
  -> Action_Runtime_Plan_JSON -> ClickExecutionGuard -> Click_Result_JSON file
- verifies dry-run click_result_v09 is saved for every case
- verifies saved click_result matches in-memory guard result
- verifies physical click is never executed and forced real-click remains blocked
- keeps full live UI, screen capture, YOLO, and real project mutation disabled
- adds test coverage for click-result publication

## V2.4.0
Snapshot Solver_Preflop click-guard eligibility check:
- adds tools/run_v2_4_snapshot_click_guard_eligibility_check.py
- runs all snapshot Pending preflop Clear_JSON cases through:
  Pending Clear_JSON -> Solver_Preflop bridge -> V2.1 adapter
  -> Action_Runtime_Plan_JSON -> ClickExecutionGuard
- verifies dry-run click-result eligibility passes for all Solver-sourced runtime plans
- verifies forced real-click request is blocked by real_click_master_not_armed
- verifies slot-boundary/button/no-repeat/plan-source guards are satisfied in dry-run mode
- keeps full live UI, screen capture, YOLO, and real project mutation disabled
- adds test coverage for Solver_Preflop click-guard eligibility

## V2.3.0
Snapshot Solver_Preflop runtime plan publication check.

## V2.2.0
Snapshot Solver_Preflop runtime source multi-case check.

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
