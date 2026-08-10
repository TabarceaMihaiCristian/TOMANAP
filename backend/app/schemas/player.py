"""API schemas for anonymous lobby players."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import StrictRequestModel


class JoinGameRequest(StrictRequestModel):
    """Anonymous display name submitted when joining a room."""

    display_name: str = Field(min_length=1, max_length=40)


class ReadyRequest(StrictRequestModel):
    """Desired lobby readiness state."""

    is_ready: bool


class PlayerResponse(BaseModel):
    """Public room membership state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    seat_number: int
    is_host: bool
    is_ready: bool
    is_connected: bool
