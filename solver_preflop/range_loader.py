from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=8)
def load_hero_ranges(path: str | None = None) -> dict[str, Any]:
    range_path = Path(path) if path else project_root() / "ranges" / "hero_preflop_ranges.json"
    with range_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("schema") != "preflop_ranges_v1":
        raise ValueError(f"Unsupported range schema: {data.get('schema')!r}")
    return data
