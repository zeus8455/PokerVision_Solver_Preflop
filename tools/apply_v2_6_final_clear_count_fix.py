from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_FILE = ROOT / "tools" / "run_v2_6_snapshot_final_clear_embedding_check.py"

OLD = '''    final_files = sorted(str(path) for path in OUT_DIR.rglob("Clear_JSON_Final/**/*.json"))
    runtime_files = sorted(str(path) for path in OUT_DIR.rglob("Action_Runtime_Plan_JSON/**/*.json"))
'''

NEW = '''    runtime_files = sorted(str(path) for path in OUT_DIR.rglob("Action_Runtime_Plan_JSON/**/*.json"))
    final_files = sorted(
        str(Path(item["final_clear"]["path"]))
        for item in results
        if isinstance(item.get("final_clear"), dict)
        and item["final_clear"].get("path")
        and item["final_clear"].get("exists") is True
    )
'''


def main() -> int:
    text = TOOL_FILE.read_text(encoding="utf-8")
    if NEW in text:
        print({"status": "already_patched", "file": str(TOOL_FILE), "final_clear_count_from_actual_paths": True})
        return 0
    if OLD not in text:
        raise RuntimeError("V2.6 final_files count anchor not found.")
    text = text.replace(OLD, NEW, 1)
    TOOL_FILE.write_text(text, encoding="utf-8")
    print({"status": "patched", "file": str(TOOL_FILE), "final_clear_count_from_actual_paths": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
