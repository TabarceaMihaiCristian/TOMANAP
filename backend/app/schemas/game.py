"""API schemas for room creation, settings, and public game state."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import GameStatus
from app.schemas.common import StrictRequestModel
from app.schemas.player import PlayerResponse


class CreateGameRequest(StrictRequestModel):
    """Host-selected settings for a new anonymous room."""

    display_name: str = Field(min_length=1, max_length=40)
    round_count: int = Field(default=5, ge=1, le=26)
    round_duration_seconds: int = Field(default=60, ge=1, le=600)


class UpdateGameSettingsRequest(StrictRequestModel):
    """Partial host-only lobby settings update."""

    round_count: int | None = Field(default=None, ge=1, le=26)
    round_duration_seconds: int | None = Field(default=None, ge=1, le=600)

    @model_validator(mode="after")
    def require_at_least_one_setting(self) -> "UpdateGameSettingsRequest":
        if self.round_count is None and self.round_duration_seconds is None:
            raise ValueError("At least one setting must be provided")
        return self


class GameResponse(BaseModel):
    """Public, token-free snapshot of a room or game."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_code: str
    status: GameStatus
    round_count: int
    round_duration_seconds: int
    players: list[PlayerResponse]
