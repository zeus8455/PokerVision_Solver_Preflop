from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET = (
    PROJECT_ROOT
    / "external"
    / "PokerVisionFinalVersionNoSolver_snapshot"
    / "PokerVision V1_2"
    / "display_analysis_cycle.py"
)

MARKER = "V2.32: inject Solver_Preflop bridge into full_state before v11 runtime"

INSERT_BLOCK = '''
            # V2.32: inject Solver_Preflop bridge into full_state before v11 runtime.
            #
            # Live failure fixed here:
            # - Pending/Decision preview path builds solver_preflop_bridge_contract later inside
            #   save_dark_and_clear_table_frame_json(...).
            # - _run_v11_stage2_runtime_safely(...) receives full_state before that late save path,
            #   so v11_stage1_runtime could not see state["solver_preflop_bridge_contract"].
            # - v11 then fell back to legacy v12_stub_* and real-click was blocked as
            #   blocked_stub_real_click, even though Solver_Preflop_Bridge was selected in preview.
            # - This block builds the same bridge from a current Clear_JSON candidate before v11 runtime.
            v232_existing_solver_preflop_bridge = state.get("solver_preflop_bridge_contract")
            if not isinstance(v232_existing_solver_preflop_bridge, dict):
                try:
                    v232_pre_runtime_clear_state = build_clear_json_from_dark_state(state)
                    if isinstance(v232_pre_runtime_clear_state, dict):
                        v232_pre_runtime_clear_state = dict(v232_pre_runtime_clear_state)
                        v232_pre_runtime_clear_state.pop("click_result", None)
                        v232_pre_runtime_solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                            clear_state=v232_pre_runtime_clear_state,
                            cycle_dir=cycle_dir,
                            table_id=slot.table_id,
                            publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES),
                        )
                        state["solver_preflop_bridge_contract"] = v232_pre_runtime_solver_preflop_bridge_contract
                        v232_bridge_payload = (
                            v232_pre_runtime_solver_preflop_bridge_contract.get("bridge_payload")
                            if isinstance(v232_pre_runtime_solver_preflop_bridge_contract, dict)
                            else None
                        )
                        v232_action_decision = (
                            v232_bridge_payload.get("action_decision")
                            if isinstance(v232_bridge_payload, dict)
                            else None
                        )
                        state["v232_pre_runtime_solver_preflop_bridge"] = {
                            "status": "built",
                            "bridge_status": (
                                v232_pre_runtime_solver_preflop_bridge_contract.get("status")
                                if isinstance(v232_pre_runtime_solver_preflop_bridge_contract, dict)
                                else None
                            ),
                            "action_decision_available": isinstance(v232_action_decision, dict),
                            "decision_id": (
                                v232_action_decision.get("decision_id")
                                if isinstance(v232_action_decision, dict)
                                else None
                            ),
                            "source": "pre_runtime_injection_before_v11_stage2",
                        }
                    else:
                        state["v232_pre_runtime_solver_preflop_bridge"] = {
                            "status": "not_built",
                            "reason": "clear_json_candidate_not_dict",
                            "source": "pre_runtime_injection_before_v11_stage2",
                        }
                except Exception as exc:
                    state["v232_pre_runtime_solver_preflop_bridge"] = {
                        "status": "error",
                        "reason": str(exc),
                        "source": "pre_runtime_injection_before_v11_stage2",
                    }
                    add_error(state, block="solver_preflop_bridge_contract", message=f"V2.32 pre-runtime bridge build failed: {exc}")
'''


def _insert_before_runtime_call(text: str) -> str:
    lines = text.splitlines(keepends=True)

    runtime_call_idx = None
    for idx, line in enumerate(lines):
        if "_run_v11_stage2_runtime_safely(" in line:
            window = "".join(lines[max(0, idx - 8): idx + 2])
            if "state[\"runtime_action\"]" in window or "state['runtime_action']" in window:
                runtime_call_idx = idx
                break

    if runtime_call_idx is None:
        for idx, line in enumerate(lines):
            if "_run_v11_stage2_runtime_safely(" in line and line.startswith(" " * 12):
                runtime_call_idx = idx
                break

    if runtime_call_idx is None:
        raise RuntimeError("Could not find _run_v11_stage2_runtime_safely call site")

    insert_idx = runtime_call_idx
    for idx in range(runtime_call_idx, max(-1, runtime_call_idx - 6), -1):
        if 'state["runtime_action"]' in lines[idx] or "state['runtime_action']" in lines[idx]:
            insert_idx = idx
            break

    lines.insert(insert_idx, INSERT_BLOCK)
    return "".join(lines)


def main() -> int:
    if not TARGET.exists():
        raise FileNotFoundError(f"Target not found: {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")

    if MARKER in text:
        print(f"[V2.32] Patch already present: {TARGET}")
        return 0

    updated = _insert_before_runtime_call(text)

    backup = TARGET.with_suffix(TARGET.suffix + ".v2_32_before_patch.bak")
    backup.write_text(text, encoding="utf-8", newline="")
    TARGET.write_text(updated, encoding="utf-8", newline="")

    print(f"[V2.32] Patched: {TARGET}")
    print(f"[V2.32] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
