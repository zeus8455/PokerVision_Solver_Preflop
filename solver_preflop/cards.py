from __future__ import annotations

RANKS_DESC = "AKQJT98765432"
SUIT_MAP = {
    "spades": "s",
    "hearts": "h",
    "diamonds": "d",
    "clubs": "c",
    "s": "s",
    "h": "h",
    "d": "d",
    "c": "c",
}


def normalize_card(card: str) -> str:
    value = str(card).strip()
    if "_" in value:
        rank, suit = value.split("_", 1)
        rank = rank.strip().upper()
        suit = suit.strip().lower()
        if rank == "10":
            rank = "T"
        if rank not in RANKS_DESC:
            raise ValueError(f"Invalid card rank: {card}")
        if suit not in SUIT_MAP:
            raise ValueError(f"Invalid card suit: {card}")
        return rank + SUIT_MAP[suit]

    if len(value) == 2:
        rank = value[0].upper()
        suit = value[1].lower()
        if rank == "1":
            raise ValueError(f"Use T for ten, got: {card}")
        if rank not in RANKS_DESC or suit not in SUIT_MAP:
            raise ValueError(f"Invalid card: {card}")
        return rank + SUIT_MAP[suit]

    raise ValueError(f"Invalid card format: {card}")


def normalize_cards(cards: list[str]) -> list[str]:
    out = [normalize_card(card) for card in cards]
    if len(out) != len(set(out)):
        raise ValueError("Duplicate cards detected")
    return out


def hand_to_class(cards: list[str]) -> str:
    if len(cards) != 2:
        raise ValueError("Hero hand must contain exactly 2 cards")
    c1, c2 = normalize_cards(cards)
    r1, r2 = c1[0], c2[0]
    s1, s2 = c1[1], c2[1]
    if r1 == r2:
        return r1 + r2
    ordered = sorted([r1, r2], key=lambda r: RANKS_DESC.index(r))
    return ordered[0] + ordered[1] + ("s" if s1 == s2 else "o")
