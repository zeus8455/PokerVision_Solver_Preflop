from solver_preflop.cards import hand_to_class, normalize_card


def test_normalize_pokervision_cards():
    assert normalize_card("J_spades") == "Js"
    assert normalize_card("7_clubs") == "7c"


def test_hand_to_class():
    assert hand_to_class(["J_spades", "7_clubs"]) == "J7o"
    assert hand_to_class(["A_spades", "K_spades"]) == "AKs"
    assert hand_to_class(["T_hearts", "T_clubs"]) == "TT"
