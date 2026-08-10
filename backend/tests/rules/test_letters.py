"""Tests for unused-letter selection and round limits."""

import random

import pytest

from app.core.constants import ALPHABET
from app.services.letters import (
    NoLettersRemainingError,
    select_unused_letter,
    validate_round_count,
)


def test_selected_letter_is_unused_and_reproducible_with_injected_rng() -> None:
    burned = set(ALPHABET) - {"Q", "Z"}

    selected = select_unused_letter(burned, rng=random.Random(4))

    assert selected in {"Q", "Z"}
    assert selected not in burned


def test_burned_romanian_diacritic_folds_to_basic_latin_letter() -> None:
    burned = set(ALPHABET) - {"S", "Z"}
    burned.add("Ș")

    assert select_unused_letter(burned) == "Z"


def test_selection_fails_when_every_letter_is_burned() -> None:
    with pytest.raises(NoLettersRemainingError):
        select_unused_letter(ALPHABET)


def test_selection_rejects_invalid_burned_letters() -> None:
    with pytest.raises(ValueError):
        select_unused_letter({"A", "7"})


@pytest.mark.parametrize("round_count", [1, 5, 26])
def test_round_count_accepts_values_supported_by_the_alphabet(round_count: int) -> None:
    assert validate_round_count(round_count) == round_count


@pytest.mark.parametrize("round_count", [0, 27, True])
def test_round_count_rejects_out_of_range_or_boolean_values(
    round_count: object,
) -> None:
    with pytest.raises(ValueError):
        validate_round_count(round_count)  # type: ignore[arg-type]
