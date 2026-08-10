"""Objective, dictionary-free validation for round answers."""

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.core.constants import MAX_ANSWER_LENGTH
from app.utilities.datetime import deadline_reached
from app.utilities.text import clean_answer, normalize_answer, normalize_letter


class ValidationCode(StrEnum):
    """Machine-readable reasons why an answer earned no points."""

    EMPTY = "empty"
    TOO_LONG = "too_long"
    WRONG_INITIAL = "wrong_initial"
    LATE = "late"
    INVALID_CHARACTERS = "invalid_characters"


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    """Cleaned answer plus its objective validation outcome."""

    original: str
    normalized: str
    is_valid: bool
    code: ValidationCode | None = None


def _result(
    original: str,
    normalized: str,
    code: ValidationCode | None = None,
) -> ValidatedAnswer:
    return ValidatedAnswer(
        original=original,
        normalized=normalized,
        is_valid=code is None,
        code=code,
    )


def _has_control_characters(value: str) -> bool:
    return any(unicodedata.category(character).startswith("C") for character in value)


def validate_answer(
    answer: str,
    *,
    selected_letter: str,
    submitted_at: datetime | None = None,
    ends_at: datetime | None = None,
    max_length: int = MAX_ANSWER_LENGTH,
) -> ValidatedAnswer:
    """Validate one answer against version-one objective rules.

    A deadline is exclusive: a submission arriving exactly at ``ends_at`` is
    late. Both timestamps must be supplied together and must be timezone-aware.
    """
    letter = normalize_letter(selected_letter).casefold()
    if (
        isinstance(max_length, bool)
        or not isinstance(max_length, int)
        or max_length < 1
    ):
        raise ValueError("max_length must be a positive integer")
    if (submitted_at is None) is not (ends_at is None):
        raise ValueError("submitted_at and ends_at must be supplied together")

    original = clean_answer(answer)
    normalized = normalize_answer(original)

    if submitted_at is not None and ends_at is not None:
        if deadline_reached(at=submitted_at, ends_at=ends_at):
            return _result(original, normalized, ValidationCode.LATE)
    if not original:
        return _result(original, normalized, ValidationCode.EMPTY)
    if len(original) > max_length:
        return _result(original, normalized, ValidationCode.TOO_LONG)
    if _has_control_characters(original):
        return _result(original, normalized, ValidationCode.INVALID_CHARACTERS)
    if not normalized.startswith(letter):
        return _result(original, normalized, ValidationCode.WRONG_INITIAL)
    return _result(original, normalized)
