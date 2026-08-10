"""Centralized display cleaning and comparison normalization."""

import re
import unicodedata

WHITESPACE = re.compile(r"\s+")
APOSTROPHES = frozenset({"'", "’", "ʼ", "`"})


def _require_text(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("answer must be a string")


def clean_answer(value: str) -> str:
    """Prepare an answer for display while retaining its spelling."""
    _require_text(value)
    compatible = unicodedata.normalize("NFKC", value)
    return WHITESPACE.sub(" ", compatible).strip()


def normalize_answer(value: str) -> str:
    """Normalize an answer for initial-letter and duplicate comparison.

    The policy is deliberately accent-insensitive. Apostrophes are removed;
    other punctuation, symbols, and control characters separate words. This
    makes forms such as ``Târgu-Mureș`` and ``Targu Mures`` compare equally.
    The original cleaned spelling remains available separately for display.
    """
    cleaned = clean_answer(value).casefold()
    decomposed = unicodedata.normalize("NFKD", cleaned)
    normalized: list[str] = []

    for character in decomposed:
        category = unicodedata.category(character)
        if category.startswith("M"):
            continue
        if character in APOSTROPHES:
            continue
        if category[0] in {"C", "P", "S", "Z"}:
            normalized.append(" ")
        else:
            normalized.append(character)

    return WHITESPACE.sub(" ", "".join(normalized)).strip()


def normalize_letter(value: str) -> str:
    """Fold one Romanian or basic Latin letter to uppercase basic Latin."""
    normalized = normalize_answer(value).upper()
    if len(normalized) != 1 or normalized < "A" or normalized > "Z":
        raise ValueError("letter must normalize to one basic Latin letter")
    return normalized
