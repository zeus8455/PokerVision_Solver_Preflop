# Version history

## V0.7.0
Solver response contract hardening:
- expands SolverDecision.to_json_dict() into an integration-ready contract
- adds source_frame_id and solver_source metadata
- adds action_runtime_hint for PokerVision click runtime bridge
- adds safety block with safe_fallback_used and real_click_allowed_by_solver
- adds input_summary and spot_debug sections
- keeps old top-level source/hero/spot/decision/identity/debug keys compatible
- adds tests for ok response and guarded fallback response

## V0.6.0
All-in guard logic:
- adds specific preflop all-in node classification
- distinguishes open jam, blind vs open jam, opener vs 3bet jam, threebettor vs 4bet jam
- detects incomplete all-in raise candidates from frame-local commitment levels
- keeps all all-in nodes in safe fallback until dedicated all-in ranges are added
- exposes all-in diagnostics in SolverDecision debug
- updates all-in tests to validate guarded behavior

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
