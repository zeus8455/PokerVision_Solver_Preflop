from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver_preflop import solve_clear_json


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python tools/solve_clear_json.py <clear_json_path>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    decision = solve_clear_json(data)
    print(json.dumps(decision.to_json_dict(), ensure_ascii=False, indent=2))
    return 0 if decision.status in {"ok", "fallback"} else 1


if __name__ == "__main__":
    raise SystemExit(main())