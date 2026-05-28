from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver_preflop import solve_clear_json
from solver_preflop.output_files import write_solver_output_files


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Solve PokerVision preflop Clear_JSON with PokerVision_Solver_Preflop.",
    )
    parser.add_argument("clear_json_path", help="Path to PokerVision preflop Clear_JSON input.")
    parser.add_argument(
        "--write-files",
        action="store_true",
        help="Write SolverDecision/ActionDecision/RuntimeHint/PokerVisionBridge JSON files.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory for --write-files. Default: input file directory.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of indented JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    path = Path(args.clear_json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    decision = solve_clear_json(data)

    if args.write_files:
        out_dir = Path(args.out_dir) if args.out_dir else path.parent
        manifest = write_solver_output_files(decision, output_dir=out_dir)
        payload = {
            "status": decision.status,
            "source_frame_id": decision.source_frame_id,
            "decision_id": decision.decision_id,
            "solver_fingerprint": decision.solver_fingerprint,
            "manifest": manifest.to_json_dict(),
        }
    else:
        payload = decision.to_json_dict()

    print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if decision.status in {"ok", "fallback"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
