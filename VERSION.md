# Version history

## V2.0.0
Snapshot-only runtime source switch scaffold:
- adds disabled-by-default snapshot toggles:
  - V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = False
  - V20_SOLVER_PREFLOP_DRY_RUN_ONLY = True
- adds _select_v20_runtime_action_decision_state(...)
- keeps old Action_Decision_JSON as runtime source by default
- prepares build_and_save_action_decision_contract(...) to accept optional solver_preflop_bridge_contract
- reorders pending-preview branch so Solver_Preflop bridge is built before Action_Decision contract and can be passed into the selector
- embeds v20_runtime_source_selection into action_decision_contract and action_runtime_plan_contract
- does not touch C:\PokerVisionFinalVersionNoSolver
- does not enable real-click Solver runtime source

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
