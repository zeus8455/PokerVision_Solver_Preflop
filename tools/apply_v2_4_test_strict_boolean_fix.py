from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_FILE = ROOT / "tests" / "test_v2_4_snapshot_click_guard_eligibility.py"

ANCHOR = '''        assert all(item["checks"].values())
'''

INSERT = '''        assert item["checks"]["runtime_ok"] is True
        assert item["checks"]["dry_run_guard_ok"] is True
        assert item["checks"]["repeat_guard_ok"] is True
        assert item["checks"]["real_click_block_ok"] is True
'''


def main() -> int:
    text = TEST_FILE.read_text(encoding="utf-8")
    if INSERT in text:
        print({"status": "already_patched", "file": str(TEST_FILE), "strict_boolean_assertions": True})
        return 0
    if ANCHOR not in text:
        raise RuntimeError("V2.4 test anchor not found.")
    text = text.replace(ANCHOR, INSERT + "\n" + ANCHOR, 1)
    TEST_FILE.write_text(text, encoding="utf-8")
    print({"status": "patched", "file": str(TEST_FILE), "strict_boolean_assertions": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
