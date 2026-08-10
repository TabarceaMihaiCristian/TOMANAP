"""Tests for deterministic category-by-category TOMANAP scoring."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.constants import CATEGORIES, Category
from app.services.scoring import ScoringSubmission, score_round
from app.services.validation import ValidationCode

STARTED_AT = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
ENDS_AT = STARTED_AT + timedelta(seconds=60)


def _answers(**overrides: str) -> dict[Category, str]:
    answers = {
        Category.COUNTRIES: "Polonia",
        Category.CITIES: "Ploiești",
        Category.BRANDS: "Pagani",
        Category.ACTIVITIES: "Ping-Pong",
        Category.NAMES: "Petru",
        Category.ANIMALS: "Pinguin",
        Category.PLANTS: "Păpădie",
    }
    answers.update({Category(key): value for key, value in overrides.items()})
    return answers


def test_single_players_valid_answers_are_all_unique() -> None:
    result = score_round(
        [ScoringSubmission("player-1", _answers(), STARTED_AT)],
        selected_letter="P",
        ends_at=ENDS_AT,
    )

    player = result.players["player-1"]
    assert player.total == 70
    assert all(player.answers[category].points == 10 for category in CATEGORIES)


def test_duplicates_are_compared_after_normalization_per_category() -> None:
    submissions = [
        ScoringSubmission("player-1", _answers(), STARTED_AT),
        ScoringSubmission(
            "player-2",
            _answers(
                countries="Portugalia",
                cities="PLOIESTI",
                activities="Pictură",
                animals="Pînguin",
                plants="",
            ),
            STARTED_AT + timedelta(seconds=5),
        ),
    ]

    result = score_round(submissions, selected_letter="P", ends_at=ENDS_AT)

    first = result.players["player-1"]
    second = result.players["player-2"]
    assert first.answers[Category.COUNTRIES].points == 10
    assert second.answers[Category.COUNTRIES].points == 10
    assert first.answers[Category.CITIES].points == 5
    assert second.answers[Category.CITIES].points == 5
    assert first.answers[Category.ANIMALS].points == 5
    assert second.answers[Category.ANIMALS].points == 5
    assert second.answers[Category.PLANTS].points == 0
    assert second.answers[Category.PLANTS].validation_code is ValidationCode.EMPTY
    assert first.total == 50
    assert second.total == 40


def test_invalid_wrong_initial_and_late_answers_score_zero() -> None:
    submissions = [
        ScoringSubmission(
            "wrong-initial",
            _answers(cities="București"),
            STARTED_AT,
        ),
        ScoringSubmission(
            "late",
            _answers(),
            ENDS_AT,
        ),
    ]

    result = score_round(submissions, selected_letter="P", ends_at=ENDS_AT)

    wrong_city = result.players["wrong-initial"].answers[Category.CITIES]
    late_country = result.players["late"].answers[Category.COUNTRIES]
    assert wrong_city.points == 0
    assert wrong_city.validation_code is ValidationCode.WRONG_INITIAL
    assert late_country.points == 0
    assert late_country.validation_code is ValidationCode.LATE
    assert result.players["late"].total == 0


def test_missing_categories_are_treated_as_empty_answers() -> None:
    result = score_round(
        [ScoringSubmission("player-1", {}, STARTED_AT)],
        selected_letter="P",
        ends_at=ENDS_AT,
    )

    assert result.players["player-1"].total == 0
    assert all(
        result.players["player-1"].answers[category].validation_code
        is ValidationCode.EMPTY
        for category in CATEGORIES
    )


def test_duplicate_player_ids_are_rejected() -> None:
    submissions = [
        ScoringSubmission("same-player", _answers(), STARTED_AT),
        ScoringSubmission("same-player", _answers(), STARTED_AT),
    ]

    with pytest.raises(ValueError, match="Duplicate player_id"):
        score_round(submissions, selected_letter="P", ends_at=ENDS_AT)
