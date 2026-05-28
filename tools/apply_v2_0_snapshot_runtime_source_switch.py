from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_FILE = ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2" / "display_analysis_cycle.py"


TOGGLE_ANCHOR = "V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES = False"
TOGGLE_INSERT = """V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES = False

# V2.0: snapshot-only runtime source switch scaffold.
# Default remains False: old Action_Decision_JSON remains the runtime source.
V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = False
V20_SOLVER_PREFLOP_DRY_RUN_ONLY = True"""

HELPER_ANCHOR = """

def build_and_save_action_runtime_plan_contract(
"""

HELPER_BLOCK = (
    "\n\n"
    "def _select_v20_runtime_action_decision_state(\n"
    "    *,\n"
    "    default_action_decision_state: Dict[str, object],\n"
    "    solver_preflop_bridge_contract: Optional[Dict[str, object]] = None,\n"
    ") -> tuple[Dict[str, object], Dict[str, object]]:\n"
    "    \"\"\"Select which Action_Decision-like payload feeds Action_Runtime_Plan_JSON.\n"
    "\n"
    "    V2.0 is deliberately disabled by default. When disabled, this function\n"
    "    always returns the legacy Action_Decision_JSON payload. When enabled later,\n"
    "    Solver_Preflop may become the source only if its bridge contract provides a\n"
    "    bridge_payload.action_decision object. This scaffold does not bypass runtime\n"
    "    guards and does not enable real-click by itself.\n"
    "    \"\"\"\n"
    "    selection = {\n"
    "        \"schema\": \"v20_runtime_action_decision_source_selection_v1\",\n"
    "        \"enabled\": bool(V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE),\n"
    "        \"selected_source\": \"Action_Decision_JSON\",\n"
    "        \"reason\": \"v20_switch_disabled\",\n"
    "        \"dry_run_only\": bool(V20_SOLVER_PREFLOP_DRY_RUN_ONLY),\n"
    "        \"solver_bridge_status\": None,\n"
    "        \"solver_action_decision_available\": False,\n"
    "    }\n"
    "\n"
    "    if not V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE:\n"
    "        return dict(default_action_decision_state), selection\n"
    "\n"
    "    if not isinstance(solver_preflop_bridge_contract, dict):\n"
    "        selection[\"reason\"] = \"solver_bridge_contract_missing\"\n"
    "        return dict(default_action_decision_state), selection\n"
    "\n"
    "    selection[\"solver_bridge_status\"] = solver_preflop_bridge_contract.get(\"status\")\n"
    "    bridge_payload = solver_preflop_bridge_contract.get(\"bridge_payload\")\n"
    "    if not isinstance(bridge_payload, dict):\n"
    "        selection[\"reason\"] = \"solver_bridge_payload_missing\"\n"
    "        return dict(default_action_decision_state), selection\n"
    "\n"
    "    solver_action_decision = bridge_payload.get(\"action_decision\")\n"
    "    if not isinstance(solver_action_decision, dict):\n"
    "        selection[\"reason\"] = \"solver_action_decision_missing\"\n"
    "        return dict(default_action_decision_state), selection\n"
    "\n"
    "    selection[\"solver_action_decision_available\"] = True\n"
    "    selection[\"selected_source\"] = \"Solver_Preflop_Bridge\"\n"
    "    selection[\"reason\"] = \"v20_solver_preflop_selected\"\n"
    "    selection[\"source_frame_id\"] = solver_action_decision.get(\"source_frame_id\")\n"
    "    selection[\"decision_id\"] = solver_action_decision.get(\"decision_id\")\n"
    "    selection[\"solver_fingerprint\"] = solver_action_decision.get(\"solver_fingerprint\")\n"
    "    return dict(solver_action_decision), selection\n"
)

SIGNATURE_OLD = """def build_and_save_action_decision_contract(
    *,
    decision_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
    publish_files: bool = True,
) -> Dict[str, object]:
"""

SIGNATURE_NEW = """def build_and_save_action_decision_contract(
    *,
    decision_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
    publish_files: bool = True,
    solver_preflop_bridge_contract: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
"""

RUNTIME_OLD = """            runtime_plan_contract = build_and_save_action_runtime_plan_contract(
                action_decision_state=action_decision_state,
                cycle_dir=cycle_dir,
                table_id=table_id,
                publish_files=publish_files,
            )
            return {
"""

RUNTIME_NEW = """            runtime_action_decision_state, v20_runtime_source_selection = _select_v20_runtime_action_decision_state(
                default_action_decision_state=action_decision_state,
                solver_preflop_bridge_contract=solver_preflop_bridge_contract,
            )
            runtime_plan_contract = build_and_save_action_runtime_plan_contract(
                action_decision_state=runtime_action_decision_state,
                cycle_dir=cycle_dir,
                table_id=table_id,
                publish_files=publish_files,
            )
            if isinstance(runtime_plan_contract, dict):
                runtime_plan_contract["v20_runtime_source_selection"] = dict(v20_runtime_source_selection)
            return {
"""

RETURN_ANCHOR = """                "action_runtime_plan_contract": runtime_plan_contract,
            }
"""

RETURN_REPLACEMENT = """                "v20_runtime_source_selection": dict(v20_runtime_source_selection),
                "action_runtime_plan_contract": runtime_plan_contract,
            }
"""

PENDING_OLD = """                            action_decision_contract = build_and_save_action_decision_contract(
                                decision_state=decision_state,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=False,
                            )
                            solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                                clear_state=clear_state_candidate,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES),
                            )
                            if isinstance(action_decision_contract, dict):
                                action_decision_contract["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract
                                state["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract
"""

PENDING_NEW = """                            solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                                clear_state=clear_state_candidate,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES),
                            )
                            action_decision_contract = build_and_save_action_decision_contract(
                                decision_state=decision_state,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=False,
                                solver_preflop_bridge_contract=solver_preflop_bridge_contract,
                            )
                            if isinstance(action_decision_contract, dict):
                                action_decision_contract["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract
                                state["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract
"""


def main() -> int:
    text = DISPLAY_FILE.read_text(encoding="utf-8")
    changed = False

    if "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = False" not in text:
        if TOGGLE_ANCHOR not in text:
            raise RuntimeError("V2.0 toggle anchor not found.")
        text = text.replace(TOGGLE_ANCHOR, TOGGLE_INSERT, 1)
        changed = True

    if "def _select_v20_runtime_action_decision_state(" not in text:
        if HELPER_ANCHOR not in text:
            raise RuntimeError("V2.0 helper anchor not found.")
        text = text.replace(HELPER_ANCHOR, HELPER_BLOCK + HELPER_ANCHOR, 1)
        changed = True

    if "solver_preflop_bridge_contract: Optional[Dict[str, object]] = None" not in text:
        if SIGNATURE_OLD not in text:
            raise RuntimeError("build_and_save_action_decision_contract signature anchor not found.")
        text = text.replace(SIGNATURE_OLD, SIGNATURE_NEW, 1)
        changed = True

    action_decision_section = text.split("def build_and_save_action_decision_contract", 1)[1]
    if "_select_v20_runtime_action_decision_state(" not in action_decision_section:
        if RUNTIME_OLD not in text:
            raise RuntimeError("Runtime source selection insertion anchor not found.")
        text = text.replace(RUNTIME_OLD, RUNTIME_NEW, 1)
        changed = True

    if '"v20_runtime_source_selection": dict(v20_runtime_source_selection)' not in text:
        if RETURN_ANCHOR not in text:
            raise RuntimeError("Action decision return anchor not found.")
        text = text.replace(RETURN_ANCHOR, RETURN_REPLACEMENT, 1)
        changed = True

    if "solver_preflop_bridge_contract=solver_preflop_bridge_contract" not in text:
        if PENDING_OLD not in text:
            raise RuntimeError("Pending preview reorder anchor not found.")
        text = text.replace(PENDING_OLD, PENDING_NEW, 1)
        changed = True

    if changed:
        DISPLAY_FILE.write_text(text, encoding="utf-8")

    print({
        "status": "patched" if changed else "already_patched",
        "file": str(DISPLAY_FILE),
        "v20_toggle_present": "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = False" in text,
        "v20_helper_present": "def _select_v20_runtime_action_decision_state(" in text,
        "v20_optional_bridge_param_present": "solver_preflop_bridge_contract: Optional[Dict[str, object]] = None" in text,
        "v20_selection_embedded": '"v20_runtime_source_selection": dict(v20_runtime_source_selection)' in text,
        "v20_pending_passes_bridge": "solver_preflop_bridge_contract=solver_preflop_bridge_contract" in text,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
