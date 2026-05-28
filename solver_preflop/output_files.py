from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import SolverDecision
from .pokervision_bridge import build_pokervision_bridge_payload


@dataclass(slots=True, frozen=True)
class SolverOutputManifest:
    source_frame_id: str
    output_dir: str
    solver_decision_json: str
    solver_action_decision_json: str
    solver_runtime_hint_json: str
    pokervision_bridge_json: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source_frame_id": self.source_frame_id,
            "output_dir": self.output_dir,
            "files": {
                "solver_decision_json": self.solver_decision_json,
                "solver_action_decision_json": self.solver_action_decision_json,
                "solver_runtime_hint_json": self.solver_runtime_hint_json,
                "pokervision_bridge_json": self.pokervision_bridge_json,
            },
        }


def _safe_stem(source_frame_id: str) -> str:
    raw = str(source_frame_id or "unknown_frame")
    out = []
    for ch in raw:
        if ch.isalnum() or ch in {"_", "-", "."}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("._") or "unknown_frame"


def build_solver_output_payloads(decision: SolverDecision) -> dict[str, dict[str, Any]]:
    full_payload = decision.to_json_dict()
    return {
        "solver_decision_json": full_payload,
        "solver_action_decision_json": decision.to_action_decision_dict(),
        "solver_runtime_hint_json": {
            "schema": "pokervision_solver_runtime_hint_json_v1",
            "source": "PokerVision_Solver_Preflop",
            "source_frame_id": decision.source_frame_id,
            "decision_id": decision.decision_id,
            "solver_fingerprint": decision.solver_fingerprint,
            "action_runtime_hint": full_payload["action_runtime_hint"],
            "safety": full_payload["safety"],
            "decision": full_payload["decision"],
            "spot_debug": full_payload["spot_debug"],
            "warnings": full_payload["warnings"],
        },
        "pokervision_bridge_json": build_pokervision_bridge_payload(decision),
    }


def write_solver_output_files(
    decision: SolverDecision,
    *,
    output_dir: str | Path,
    overwrite: bool = True,
) -> SolverOutputManifest:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = _safe_stem(decision.source_frame_id)
    paths = {
        "solver_decision_json": out_dir / f"{stem}_SolverDecision_JSON.json",
        "solver_action_decision_json": out_dir / f"{stem}_SolverActionDecision_JSON.json",
        "solver_runtime_hint_json": out_dir / f"{stem}_SolverRuntimeHint_JSON.json",
        "pokervision_bridge_json": out_dir / f"{stem}_PokerVisionBridge_JSON.json",
    }

    if not overwrite:
        existing = [str(path) for path in paths.values() if path.exists()]
        if existing:
            raise FileExistsError(f"Output file(s) already exist: {existing}")

    payloads = build_solver_output_payloads(decision)
    for key, path in paths.items():
        path.write_text(
            json.dumps(payloads[key], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return SolverOutputManifest(
        source_frame_id=decision.source_frame_id,
        output_dir=str(out_dir),
        solver_decision_json=str(paths["solver_decision_json"]),
        solver_action_decision_json=str(paths["solver_action_decision_json"]),
        solver_runtime_hint_json=str(paths["solver_runtime_hint_json"]),
        pokervision_bridge_json=str(paths["pokervision_bridge_json"]),
    )
