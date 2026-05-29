from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION.md"

NOTE = "- V2.6 count fix: final Clear_JSON file count is derived from actual saved final_clear.path values, because the snapshot final dir resolves to Clear_JSON rather than Clear_JSON_Final."


def main() -> int:
    text = VERSION_FILE.read_text(encoding="utf-8")
    if NOTE in text:
        print({"status": "already_patched", "file": str(VERSION_FILE)})
        return 0

    marker = "## V2.6.0\n"
    if marker not in text:
        raise RuntimeError("V2.6.0 section not found in VERSION.md.")

    idx = text.index(marker) + len(marker)
    next_section = text.find("\n## ", idx)
    if next_section == -1:
        next_section = len(text)

    section = text[idx:next_section].rstrip() + "\n" + NOTE + "\n"
    text = text[:idx] + section + text[next_section:]
    VERSION_FILE.write_text(text, encoding="utf-8")
    print({"status": "patched", "file": str(VERSION_FILE)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
