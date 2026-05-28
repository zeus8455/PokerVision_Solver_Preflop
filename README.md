# PokerVision_Solver_Preflop

V0.1 skeleton for the standalone PokerVision preflop solver.

Goal:
Clear_JSON from PokerVision Active preflop spot -> Solver decision contract -> PokerVision guarded click runtime.

Current V0.1 scope:
- strict contracts
- card normalization
- Clear_JSON adapter
- basic preflop spot classifier
- sizing/click policy
- CLI smoke tool
- tests for BB vs limp example

Important PokerVision rules:
- chips: false means 0bb committed, not missing detection
- fold: false means player is still in the hand
- all_in field may be absent; absent means False
- all_in: true + numeric chips means the player is all-in for that committed amount
- preflop check is inferred logically, not detected
