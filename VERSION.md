# Version history

## V0.9.0
PokerVision integration bridge preview:
- adds solver_preflop/pokervision_bridge.py
- builds a PokerVision-facing bridge payload from SolverDecision
- adds runtime_plan_candidate with button_sequence/target_buttons
- output_files.py now writes:
  - *_SolverDecision_JSON.json
  - *_SolverActionDecision_JSON.json
  - *_SolverRuntimeHint_JSON.json
  - *_PokerVisionBridge_JSON.json
- CLI --write-files now includes PokerVisionBridge JSON
- adds tests for bridge payload and bridge file output

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
