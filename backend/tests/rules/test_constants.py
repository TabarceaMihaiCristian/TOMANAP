"""Tests that pin down the first-version TOMANAP rules."""

from app.core.constants import (
    ALPHABET,
    CATEGORIES,
    DEFAULT_ROUND_DURATION_SECONDS,
    DUPLICATE_ANSWER_POINTS,
    MAX_PLAYERS,
    MAX_ROUNDS,
    MIN_PLAYERS,
    UNIQUE_ANSWER_POINTS,
    Category,
)


def test_game_constants_match_the_agreed_rules() -> None:
    assert CATEGORIES == (
        Category.COUNTRIES,
        Category.CITIES,
        Category.BRANDS,
        Category.ACTIVITIES,
        Category.NAMES,
        Category.ANIMALS,
        Category.PLANTS,
    )
    assert ALPHABET == tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert MIN_PLAYERS == 2
    assert MAX_PLAYERS == 6
    assert DEFAULT_ROUND_DURATION_SECONDS == 60
    assert MAX_ROUNDS == len(ALPHABET) == 26
    assert UNIQUE_ANSWER_POINTS == 10
    assert DUPLICATE_ANSWER_POINTS == 5
