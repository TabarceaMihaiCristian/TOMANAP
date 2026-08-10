"""API schemas for complete seven-category submission snapshots."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import StrictRequestModel


class SubmissionAnswers(StrictRequestModel):
    """All seven category answers sent as one replaceable draft."""

    countries: str = Field(default="", max_length=80)
    cities: str = Field(default="", max_length=80)
    brands: str = Field(default="", max_length=80)
    activities: str = Field(default="", max_length=80)
    names: str = Field(default="", max_length=80)
    animals: str = Field(default="", max_length=80)
    plants: str = Field(default="", max_length=80)


class SubmissionUpsertRequest(StrictRequestModel):
    """Whole-draft replacement before finalization or deadline."""

    answers: SubmissionAnswers


class SubmissionResponse(BaseModel):
    """The caller's persisted draft or finalized submission."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    round_id: UUID
    player_id: UUID
    answers: dict[str, str]
    normalized_answers: dict[str, str]
    is_finalized: bool
    submitted_at: datetime | None
    finalized_at: datetime | None
    revision: int
