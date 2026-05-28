import json
from pathlib import Path

from solver_preflop import solve_clear_json


def test_bb_vs_limp_returns_check_in_v01():
    path = Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    decision = solve_clear_json(data)

    assert decision.status == "ok"
    assert decision.hero_position == "BB"
    assert decision.hand_class == "J7o"
    assert decision.node_type == "bb_option_vs_1_limper"
    assert decision.raw_action == "check"
    assert decision.click_sequence == ["Check"]
