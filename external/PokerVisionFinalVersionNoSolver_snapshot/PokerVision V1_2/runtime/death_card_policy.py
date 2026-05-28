r"""
runtime/death_card_policy.py

PokerVision Core V1.1 — single global dead-range policy for Non_active_fold.

Purpose:
- load C:\PokerVision\Data_death_card\data_death_card.json;
- normalize exactly two HERO cards to poker hand key: AA / AKs / AKo;
- compare by suited/off-suit correctly;
- return deterministic match/no-match report.

This module does not click and does not run YOLO.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import (
    V11_DEATH_CARD_DIR,
    V11_DEATH_CARD_FILE_NAME,
    V11_DEATH_CARD_STRICT_ENABLED_REQUIRED,
)

RANK_ORDER: Dict[str, int] = {
    "A": 14,
    "K": 13,
    "Q": 12,
    "J": 11,
    "T": 10,
    "10": 10,
    "9": 9,
    "8": 8,
    "7": 7,
    "6": 6,
    "5": 5,
    "4": 4,
    "3": 3,
    "2": 2,
}

RANK_ALIASES: Dict[str, str] = {
    "A": "A",
    "ACE": "A",
    "K": "K",
    "KING": "K",
    "Q": "Q",
    "QUEEN": "Q",
    "J": "J",
    "JACK": "J",
    "T": "T",
    "10": "T",
    "TEN": "T",
    "9": "9",
    "8": "8",
    "7": "7",
    "6": "6",
    "5": "5",
    "4": "4",
    "3": "3",
    "2": "2",
}

SUIT_ALIASES: Dict[str, str] = {
    "s": "spades",
    "spade": "spades",
    "spades": "spades",
    "h": "hearts",
    "heart": "hearts",
    "hearts": "hearts",
    "d": "diamonds",
    "diamond": "diamonds",
    "diamonds": "diamonds",
    "c": "clubs",
    "club": "clubs",
    "clubs": "clubs",
}


def _canonical_rank(raw_rank: str) -> str:
    key = str(raw_rank).strip().upper()
    if key not in RANK_ALIASES:
        raise ValueError(f"Unknown card rank: {raw_rank!r}")
    return RANK_ALIASES[key]


def _canonical_suit(raw_suit: str) -> str:
    key = str(raw_suit).strip().lower()
    if key not in SUIT_ALIASES:
        raise ValueError(f"Unknown card suit: {raw_suit!r}")
    return SUIT_ALIASES[key]


def parse_card_name(card_name: str) -> Tuple[str, str]:
    """
    Parse Card_Detector class name into (rank, suit).

    Supported examples:
    - "10_diamonds"
    - "A_spades"
    - "Q_hearts"
    - "7_clubs"
    """
    text = str(card_name).strip()
    if not text:
        raise ValueError("Empty card name")

    if "_" in text:
        rank_raw, suit_raw = text.split("_", 1)
    elif "-" in text:
        rank_raw, suit_raw = text.split("-", 1)
    else:
        raise ValueError(f"Card name must contain '_' or '-': {card_name!r}")

    return _canonical_rank(rank_raw), _canonical_suit(suit_raw)


def normalize_hero_cards_to_hand_key(hero_cards: List[str]) -> str:
    """
    Convert exactly two concrete cards to a 169-matrix key.

    Rules:
    - pair: AA, KK, QQ, ...
    - suited non-pair: AKs, T9s, 96s
    - offsuit non-pair: AKo, T9o, 96o
    - high rank always goes first.
    """
    clean = [str(card).strip() for card in hero_cards if str(card).strip()]
    if len(clean) != 2:
        raise ValueError(f"Expected exactly 2 HERO cards, got {len(clean)}: {hero_cards!r}")
    if clean[0] == clean[1]:
        raise ValueError(f"Duplicate HERO card classes are not allowed: {hero_cards!r}")

    first_rank, first_suit = parse_card_name(clean[0])
    second_rank, second_suit = parse_card_name(clean[1])

    if first_rank == second_rank:
        return f"{first_rank}{second_rank}"

    first_value = RANK_ORDER[first_rank]
    second_value = RANK_ORDER[second_rank]
    if first_value >= second_value:
        high, low = first_rank, second_rank
    else:
        high, low = second_rank, first_rank

    suffix = "s" if first_suit == second_suit else "o"
    return f"{high}{low}{suffix}"


def get_death_card_path(path: Optional[Path] = None) -> Path:
    if path is not None:
        return Path(path)
    return Path(V11_DEATH_CARD_DIR) / V11_DEATH_CARD_FILE_NAME


def load_death_card_range(path: Optional[Path] = None) -> Dict[str, Any]:
    death_path = get_death_card_path(path)
    if not death_path.exists():
        raise FileNotFoundError(f"Death-card range file not found: {death_path}")

    payload = json.loads(death_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Death-card range must be JSON object: {death_path}")

    if V11_DEATH_CARD_STRICT_ENABLED_REQUIRED and payload.get("enabled") is not True:
        raise ValueError(f"Death-card range file is not enabled: {death_path}")

    hands = payload.get("hands")
    if not isinstance(hands, list):
        raise ValueError(f"Death-card range must contain hands list: {death_path}")

    normalized_hands = sorted({str(hand).strip() for hand in hands if str(hand).strip()})
    payload["hands"] = normalized_hands
    payload["hands_set"] = set(normalized_hands)
    payload["path"] = str(death_path)
    return payload


def check_hero_cards_in_death_range(hero_cards: List[str], *, path: Optional[Path] = None) -> Dict[str, Any]:
    """Return a runtime-safe match report for Non_active_fold."""
    report: Dict[str, Any] = {
        "status": "skipped",
        "path": str(get_death_card_path(path)),
        "hero_cards": list(hero_cards or []),
        "hand_key": None,
        "matched": False,
        "message": None,
    }

    try:
        hand_key = normalize_hero_cards_to_hand_key(hero_cards)
        death_range = load_death_card_range(path)
        matched = hand_key in death_range["hands_set"]
        report.update(
            {
                "status": "matched" if matched else "not_matched",
                "hand_key": hand_key,
                "matched": bool(matched),
                "range_id": death_range.get("range_id"),
                "range_name": death_range.get("range_name"),
                "hands_count": len(death_range.get("hands") or []),
                "message": "Hero hand is inside death-card range." if matched else "Hero hand is not inside death-card range.",
            }
        )
    except Exception as exc:
        report.update({"status": "error", "message": str(exc), "matched": False})

    return report
