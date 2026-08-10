"""Deterministic, category-by-category TOMANAP scoring."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from app.core.constants import (
    CATEGORIES,
    DUPLICATE_ANSWER_POINTS,
    INVALID_ANSWER_POINTS,
    UNIQUE_ANSWER_POINTS,
    Category,
)
from app.services.validation import (
    ValidatedAnswer,
    ValidationCode,
    validate_answer,
)
from app.utilities.datetime import require_aware
from app.utilities.text import normalize_letter


@dataclass(frozen=True, slots=True)
class ScoringSubmission:
    """A player's authoritative submission presented to the scoring engine."""

    player_id: str
    answers: Mapping[Category | str, str]
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class ScoredAnswer:
    """One validated answer and its awarded points."""

    original: str
    normalized: str
    is_valid: bool
    validation_code: ValidationCode | None
    points: int


@dataclass(frozen=True, slots=True)
class PlayerRoundScore:
    """A complete seven-category score for one player."""

    player_id: str
    answers: Mapping[Category, ScoredAnswer]
    total: int


@dataclass(frozen=True, slots=True)
class RoundScore:
    """Immutable scoring result for an entire round."""

    selected_letter: str
    ends_at: datetime
    players: Mapping[str, PlayerRoundScore]


def _validate_submission_shape(submission: ScoringSubmission) -> None:
    if not isinstance(submission.player_id, str) or not submission.player_id.strip():
        raise ValueError("player_id must be a non-empty string")
    require_aware(submission.submitted_at, name="submitted_at")
    for category, answer in submission.answers.items():
        try:
            Category(category)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unknown answer category: {category!r}") from error
        if not isinstance(answer, str):
            raise TypeError(f"Answer for {category!s} must be a string")


def _validate_submissions(
    submissions: list[ScoringSubmission],
    *,
    selected_letter: str,
    ends_at: datetime,
) -> dict[str, dict[Category, ValidatedAnswer]]:
    validated: dict[str, dict[Category, ValidatedAnswer]] = {}
    for submission in submissions:
        _validate_submission_shape(submission)
        if submission.player_id in validated:
            raise ValueError(f"Duplicate player_id: {submission.player_id}")
        validated[submission.player_id] = {
            category: validate_answer(
                submission.answers.get(category, ""),
                selected_letter=selected_letter,
                submitted_at=submission.submitted_at,
                ends_at=ends_at,
            )
            for category in CATEGORIES
        }
    return validated


def score_round(
    submissions: list[ScoringSubmission] | tuple[ScoringSubmission, ...],
    *,
    selected_letter: str,
    ends_at: datetime,
) -> RoundScore:
    """Validate and score all submissions without mutating the inputs."""
    normalized_letter = normalize_letter(selected_letter)
    checked_ends_at = require_aware(ends_at, name="ends_at")
    materialized = list(submissions)
    validated = _validate_submissions(
        materialized,
        selected_letter=normalized_letter,
        ends_at=checked_ends_at,
    )

    duplicate_counts = {
        category: Counter(
            answers[category].normalized
            for answers in validated.values()
            if answers[category].is_valid
        )
        for category in CATEGORIES
    }

    players: dict[str, PlayerRoundScore] = {}
    for player_id, answers in validated.items():
        scored_answers: dict[Category, ScoredAnswer] = {}
        for category, answer in answers.items():
            if not answer.is_valid:
                points = INVALID_ANSWER_POINTS
            elif duplicate_counts[category][answer.normalized] > 1:
                points = DUPLICATE_ANSWER_POINTS
            else:
                points = UNIQUE_ANSWER_POINTS
            scored_answers[category] = ScoredAnswer(
                original=answer.original,
                normalized=answer.normalized,
                is_valid=answer.is_valid,
                validation_code=answer.code,
                points=points,
            )
        immutable_answers = MappingProxyType(scored_answers)
        players[player_id] = PlayerRoundScore(
            player_id=player_id,
            answers=immutable_answers,
            total=sum(answer.points for answer in immutable_answers.values()),
        )

    return RoundScore(
        selected_letter=normalized_letter,
        ends_at=checked_ends_at,
        players=MappingProxyType(players),
    )
