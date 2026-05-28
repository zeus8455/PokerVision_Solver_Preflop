# Version history

## V1.2.0
PokerVision dry-run preflop solver bridge preview:
- adds PokerVision snapshot runtime/solver_preflop_dryrun_bridge.py
- adds apply tool that inserts a dry-run solver bridge preview into display_analysis_cycle.py after pending Action_Decision preview construction
- does not change real-click runtime behavior
- bridge runs only for preflop Clear_JSON candidates without click_result
- bridge output is embedded into action_decision_contract as solver_preflop_bridge_contract
- optional diagnostic file publication is disabled by default

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
