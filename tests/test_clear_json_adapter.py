import json
from pathlib import Path

from solver_preflop.clear_json_adapter import parse_clear_json_preflop


def test_chips_false_means_zero_committed():
    path = Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    frame = parse_clear_json_preflop(data)
    assert frame.players["UTG"].committed_bb == 0.0
    assert frame.players["UTG"].active_in_hand is True
    assert frame.players["CO"].folded is True
