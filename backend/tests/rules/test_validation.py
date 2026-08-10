"""Tests for objective answer validation rules."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.constants import MAX_ANSWER_LENGTH
from app.services.validation import ValidationCode, validate_answer

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
DEADLINE = NOW + timedelta(seconds=60)


def test_valid_answer_is_cleaned_and_normalized() -> None:
    result = validate_answer(
        "  Pădurea   Neagră ",
        selected_letter="P",
        submitted_at=NOW,
        ends_at=DEADLINE,
    )

    assert result.is_valid is True
    assert result.code is None
    assert result.original == "Pădurea Neagră"
    assert result.normalized == "padurea neagra"


@pytest.mark.parametrize(
    ("answer", "letter", "code"),
    [
        ("  ", "P", ValidationCode.EMPTY),
        ("București", "P", ValidationCode.WRONG_INITIAL),
        ("P\x00loiești", "P", ValidationCode.INVALID_CHARACTERS),
        ("P" * (MAX_ANSWER_LENGTH + 1), "P", ValidationCode.TOO_LONG),
    ],
)
def test_invalid_objective_rules_return_specific_codes(
    answer: str,
    letter: str,
    code: ValidationCode,
) -> None:
    result = validate_answer(
        answer,
        selected_letter=letter,
        submitted_at=NOW,
        ends_at=DEADLINE,
    )

    assert result.is_valid is False
    assert result.code is code


@pytest.mark.parametrize(
    "submitted_at", [DEADLINE, DEADLINE + timedelta(microseconds=1)]
)
def test_deadline_is_exclusive(submitted_at: datetime) -> None:
    result = validate_answer(
        "Polonia",
        selected_letter="P",
        submitted_at=submitted_at,
        ends_at=DEADLINE,
    )

    assert result.is_valid is False
    assert result.code is ValidationCode.LATE


def test_naive_deadline_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_answer(
            "Polonia",
            selected_letter="P",
            submitted_at=NOW.replace(tzinfo=None),
            ends_at=DEADLINE,
        )


def test_invalid_selected_letter_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        validate_answer("Polonia", selected_letter="PP")
