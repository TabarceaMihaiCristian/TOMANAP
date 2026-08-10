"""Tests for centralized answer normalization."""

import pytest

from app.utilities.text import clean_answer, normalize_answer, normalize_letter


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Ștefan   cel Mare  ", "stefan cel mare"),
        ("ŢARĂ", "tara"),
        ("Pînguin", "pinguin"),
        ("A\u0302nghel", "anghel"),
        ("Târgu-Mureș", "targu mures"),
        ("Coca—Cola!!!", "coca cola"),
        ("O'Connor", "oconnor"),
        ("\t  ", ""),
    ],
)
def test_normalize_answer_has_a_deliberate_diacritic_and_punctuation_policy(
    raw: str,
    expected: str,
) -> None:
    assert normalize_answer(raw) == expected


def test_clean_answer_preserves_display_text_but_normalizes_spacing() -> None:
    assert clean_answer("  Târgu   Mureș  ") == "Târgu Mureș"


@pytest.mark.parametrize(("raw", "expected"), [("P", "P"), ("ș", "S")])
def test_normalize_letter_folds_romanian_diacritics(
    raw: str,
    expected: str,
) -> None:
    assert normalize_letter(raw) == expected


@pytest.mark.parametrize("raw", ["", "AB", "1", "-"])
def test_normalize_letter_rejects_non_letters(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_letter(raw)


def test_normalization_rejects_non_string_values() -> None:
    with pytest.raises(TypeError):
        normalize_answer(None)  # type: ignore[arg-type]
