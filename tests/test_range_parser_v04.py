from solver_preflop.range_parser import expand_range_text, hand_in_range


def test_expand_pairs_plus():
    expanded = expand_range_text("TT+")
    assert "TT" in expanded
    assert "JJ" in expanded
    assert "AA" in expanded
    assert "99" not in expanded


def test_expand_suited_plus_fixed_high():
    expanded = expand_range_text("KTs+")
    assert "KTs" in expanded
    assert "KJs" in expanded
    assert "KQs" in expanded
    assert "K9s" not in expanded


def test_expand_offsuit_plus():
    expanded = expand_range_text("ATo+")
    assert "ATo" in expanded
    assert "AJo" in expanded
    assert "AQo" in expanded
    assert "AKo" in expanded
    assert "A9o" not in expanded


def test_dash_ranges():
    expanded = expand_range_text("22-99 K2s-KQs")
    assert "22" in expanded
    assert "99" in expanded
    assert "TT" not in expanded
    assert "K2s" in expanded
    assert "KQs" in expanded


def test_hand_in_range():
    assert hand_in_range("AQo", "ATo+")
    assert not hand_in_range("A9o", "ATo+")
