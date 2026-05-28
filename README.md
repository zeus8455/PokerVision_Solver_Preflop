# PokerVision_Solver_Preflop

Standalone preflop Solver for PokerVision.

Current baseline: **V1.0.0 pre-integration stabilization**.

## Purpose

Input:

```text
PokerVision Clear_JSON from an Active preflop spot, before click_result
```

Output:

```text
SolverDecision JSON
SolverActionDecision JSON
SolverRuntimeHint JSON
PokerVisionBridge JSON
```

Future full chain:

```text
PokerVision Active preflop
-> Clear_JSON without click_result
-> PokerVision_Solver_Preflop
-> PokerVision bridge/action decision/runtime hint
-> PokerVision guarded click runtime
-> Final Clear_JSON with click_result
```

## Core PokerVision rules

- `chips: false` means **0bb committed**, not missing detection.
- `fold: false` means the player is still in the hand, even with `chips: false`.
- `all_in` is absent unless true.
- `all_in: true` plus numeric `chips` means the player is all-in for that committed amount.
- Preflop check is inferred logically. Example: BB vs limp with `to_call_bb = 0` can check.
- Safe fallback click sequence is always:

```text
Check -> Check/fold -> FOLD
```

## Click mapping

```text
open_raise  -> Raise
iso_raise   -> 98% -> Raise
3bet        -> 98% -> Raise
4bet        -> 50% -> Raise
5bet        -> 50% -> Raise
jam/all_in  -> 98% -> Raise
check       -> Check
call        -> CALL
fold        -> FOLD
```

## Run tests

```powershell
cd "C:\PokerVision_Solver_Preflop"

C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe -m pytest
```

## Solve one Clear_JSON

```powershell
cd "C:\PokerVision_Solver_Preflop"

C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe tools\solve_clear_json.py `
  examples\clear_json\table_02_hand_29_preflop_01_preclick.json
```

## Write solver output files

```powershell
cd "C:\PokerVision_Solver_Preflop"

C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe tools\solve_clear_json.py `
  examples\clear_json\table_02_hand_29_preflop_01_preclick.json `
  --write-files `
  --out-dir ".\tmp_solver_outputs"
```

Expected files:

```text
*_SolverDecision_JSON.json
*_SolverActionDecision_JSON.json
*_SolverRuntimeHint_JSON.json
*_PokerVisionBridge_JSON.json
```

## Pre-integration check

```powershell
cd "C:\PokerVision_Solver_Preflop"

C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe tools\run_preintegration_check.py
```

This runs the test suite and verifies the CLI/bridge output path.
