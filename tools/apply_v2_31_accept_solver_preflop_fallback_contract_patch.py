from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET = (
    PROJECT_ROOT
    / "external"
    / "PokerVisionFinalVersionNoSolver_snapshot"
    / "PokerVision V1_2"
    / "runtime"
    / "v11_stage1_runtime.py"
)

MARKER = "V2.31: accept Solver_Preflop fallback bridge when action_decision is available"

OLD = '''    if str(contract.get("status") or "") != "ok":
        return None

    bridge_payload = contract.get("bridge_payload")
'''

NEW = '''    # V2.31: accept Solver_Preflop fallback bridge when action_decision is available.
    #
    # Live failure fixed here:
    # - display/runtime source selection can correctly choose Solver_Preflop_Bridge with
    #   solver_action_decision_available=True while the bridge contract status is "fallback"
    #   for conservative unsupported nodes such as multi_raise_unknown.
    # - The previous extractor accepted only status == "ok", returned None for fallback,
    #   and run_v11_stage1_runtime then built the legacy v12_stub_* decision.
    # - Real-click is explicitly blocked for legacy v12 stubs, so the poker Action_Button
    #   click branch never executed even though Solver_Preflop had a usable safe fold/check/call decision.
    contract_status = str(contract.get("status") or "")
    if contract_status not in {"ok", "fallback"}:
        return None

    bridge_payload = contract.get("bridge_payload")
'''


def main() -> int:
    if not TARGET.exists():
        raise FileNotFoundError(f"Target not found: {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")

    if MARKER in text:
        print(f"[V2.31] Patch already present: {TARGET}")
        return 0

    if OLD not in text:
        raise RuntimeError("Could not find strict Solver_Preflop bridge status anchor in v11_stage1_runtime.py")

    updated = text.replace(OLD, NEW, 1)

    backup = TARGET.with_suffix(TARGET.suffix + ".v2_31_before_patch.bak")
    backup.write_text(text, encoding="utf-8", newline="")
    TARGET.write_text(updated, encoding="utf-8", newline="")

    print(f"[V2.31] Patched: {TARGET}")
    print(f"[V2.31] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
