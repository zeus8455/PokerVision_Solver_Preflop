from __future__ import annotations

from functools import lru_cache

RANKS = "AKQJT98765432"
RANK_TO_INDEX = {rank: index for index, rank in enumerate(RANKS)}

BROKEN_TOKEN_REPLACEMENTS = {
    "53s-98s": "53s 64s 75s 86s 97s 98s",
    "54s-98s": "54s 65s 76s 87s 98s",
    "64s-98s": "64s 75s 86s 97s 98s",
    "65s-98s": "65s 76s 87s 98s",
    "QJo-JTo": "QJo JTo",
}


def _sort_ranks(a: str, b: str) -> tuple[str, str]:
    a = a.upper()
    b = b.upper()
    if a not in RANK_TO_INDEX or b not in RANK_TO_INDEX:
        raise ValueError(f"Invalid ranks: {a}, {b}")
    return (a, b) if RANK_TO_INDEX[a] < RANK_TO_INDEX[b] else (b, a)


def _split_range_text(text: str) -> list[str]:
    fixed = str(text or "")
    for bad, replacement in BROKEN_TOKEN_REPLACEMENTS.items():
        fixed = fixed.replace(bad, replacement)
        fixed = fixed.replace(bad.upper(), replacement)
    fixed = fixed.replace(",", " ").replace(";", " ")
    return [token.strip() for token in fixed.split() if token.strip()]


def _expand_single(token: str) -> list[str]:
    token = token.strip()
    if not token:
        return []

    upper = token.upper()

    if len(upper) == 2:
        a, b = upper[0], upper[1]
        if a == b and a in RANK_TO_INDEX:
            return [a + b]
        if a in RANK_TO_INDEX and b in RANK_TO_INDEX:
            hi, lo = _sort_ranks(a, b)
            return [hi + lo + "s", hi + lo + "o"]

    if len(token) == 3:
        a = token[0].upper()
        b = token[1].upper()
        suffix = token[2].lower()
        if a in RANK_TO_INDEX and b in RANK_TO_INDEX and suffix in {"s", "o"} and a != b:
            hi, lo = _sort_ranks(a, b)
            return [hi + lo + suffix]

    raise ValueError(f"Could not parse range token: {token}")


def _expand_plus(base: str) -> list[str]:
    base = base.strip()
    upper = base.upper()

    if len(upper) == 2 and upper[0] == upper[1]:
        start = RANK_TO_INDEX[upper[0]]
        return [RANKS[i] * 2 for i in range(start, -1, -1)]

    if len(base) == 3:
        hi = base[0].upper()
        lo = base[1].upper()
        suffix = base[2].lower()
        if suffix not in {"s", "o"} or hi == lo:
            raise ValueError(f"Invalid plus token: {base}+")
        hi, lo = _sort_ranks(hi, lo)
        hi_idx = RANK_TO_INDEX[hi]
        lo_idx = RANK_TO_INDEX[lo]
        # Fixed-high expansion, matching the old advisor's practical chart style:
        # ATo+ -> ATo AJo AQo AKo
        # KTs+ -> KTs KJs KQs
        return [hi + RANKS[i] + suffix for i in range(lo_idx, hi_idx, -1)]

    raise ValueError(f"Could not parse plus token: {base}+")


def _expand_dash(left: str, right: str) -> list[str]:
    left = left.strip()
    right = right.strip()
    l_up = left.upper()
    r_up = right.upper()

    if len(l_up) == 2 and len(r_up) == 2 and l_up[0] == l_up[1] and r_up[0] == r_up[1]:
        l_idx = RANK_TO_INDEX[l_up[0]]
        r_idx = RANK_TO_INDEX[r_up[0]]
        lo, hi = sorted((l_idx, r_idx))
        return [RANKS[i] * 2 for i in range(lo, hi + 1)]

    if len(left) == 3 and len(right) == 3 and left[2].lower() == right[2].lower():
        suffix = left[2].lower()
        l_hi, l_lo = _sort_ranks(left[0], left[1])
        r_hi, r_lo = _sort_ranks(right[0], right[1])

        if l_hi == r_hi and l_lo != r_lo:
            idx1 = RANK_TO_INDEX[l_lo]
            idx2 = RANK_TO_INDEX[r_lo]
            lo, hi = sorted((idx1, idx2))
            return [l_hi + RANKS[i] + suffix for i in range(lo, hi + 1) if RANKS[i] != l_hi]

        if l_lo == r_lo and l_hi != r_hi:
            idx1 = RANK_TO_INDEX[l_hi]
            idx2 = RANK_TO_INDEX[r_hi]
            lo, hi = sorted((idx1, idx2))
            return [RANKS[i] + l_lo + suffix for i in range(lo, hi + 1) if RANKS[i] != l_lo]

    raise ValueError(f"Could not parse dash token: {left}-{right}")


def expand_token(token: str) -> frozenset[str]:
    token = str(token).strip()
    if not token:
        return frozenset()
    if "-" in token:
        left, right = token.split("-", 1)
        return frozenset(_expand_dash(left, right))
    if token.endswith("+"):
        return frozenset(_expand_plus(token[:-1]))
    return frozenset(_expand_single(token))


@lru_cache(maxsize=4096)
def expand_range_text(text: str) -> frozenset[str]:
    out: set[str] = set()
    for token in _split_range_text(text):
        out.update(expand_token(token))
    return frozenset(out)


def hand_in_range(hand_class: str, range_text: str) -> bool:
    return str(hand_class) in expand_range_text(str(range_text or ""))
