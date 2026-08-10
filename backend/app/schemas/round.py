"""API schemas for current rounds, reviews, and advancement."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.constants import Category
from app.models.enums import GameStatus, RoundStatus
from app.schemas.submission import SubmissionResponse


class RoundResponse(BaseModel):
    """Authoritative selected letter and timer state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence_number: int
    letter: str
    status: RoundStatus
    is_current: bool
    starts_at: datetime | None
    ends_at: datetime | None


class CurrentRoundResponse(BaseModel):
    """Current round plus only the requesting player's submission."""

    round: RoundResponse
    categories: tuple[Category, ...]
    submission: SubmissionResponse | None


class ScoredAnswerResponse(BaseModel):
    """Auditable score for one category answer."""

    category: Category
    original_answer: str
    normalized_answer: str
    points: int
    validation_code: str | None


class PlayerReviewResponse(BaseModel):
    """One player's complete round result."""

    player_id: UUID
    display_name: str
    total_score: int
    answers: list[ScoredAnswerResponse]


class RoundReviewResponse(BaseModel):
    """All answer and score results for a closed round."""

    round_id: UUID
    letter: str
    status: RoundStatus
    players: list[PlayerReviewResponse]


class RoundAdvanceResponse(BaseModel):
    """Next active round or final game completion."""

    game_status: GameStatus
    current_round: RoundResponse | None
