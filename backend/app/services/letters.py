"""Unbiased selection of unburned letters and round-limit validation."""

import secrets
from collections.abc import Collection, Sequence
from random import Random

from app.core.constants import ALPHABET, MIN_ROUNDS
from app.utilities.text import normalize_letter


class NoLettersRemainingError(RuntimeError):
    """Raised when every selectable letter has already been burned."""


def _normalize_alphabet(alphabet: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(normalize_letter(letter) for letter in alphabet)
    if not normalized:
        raise ValueError("alphabet must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError("alphabet must not contain duplicate letters")
    return normalized


def select_unused_letter(
    burned_letters: Collection[str],
    *,
    rng: Random | None = None,
    alphabet: Sequence[str] = ALPHABET,
) -> str:
    """Select uniformly from the letters not yet burned in this game."""
    available_alphabet = _normalize_alphabet(alphabet)
    allowed = set(available_alphabet)
    burned = {normalize_letter(letter) for letter in burned_letters}
    unknown = burned - allowed
    if unknown:
        joined = ", ".join(sorted(unknown))
        raise ValueError(f"burned letters are outside the alphabet: {joined}")

    available = tuple(letter for letter in available_alphabet if letter not in burned)
    if not available:
        raise NoLettersRemainingError("No unused letters remain")
    if rng is not None:
        return rng.choice(available)
    return secrets.choice(available)


def validate_round_count(
    round_count: int,
    *,
    alphabet: Sequence[str] = ALPHABET,
) -> int:
    """Validate that every configured round can receive a unique letter."""
    maximum = len(_normalize_alphabet(alphabet))
    if isinstance(round_count, bool) or not isinstance(round_count, int):
        raise ValueError("round_count must be an integer")
    if not MIN_ROUNDS <= round_count <= maximum:
        raise ValueError(f"round_count must be between {MIN_ROUNDS} and {maximum}")
    return round_count
