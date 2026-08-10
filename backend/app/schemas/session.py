"""API schemas for issuing and restoring anonymous sessions."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import StrictRequestModel
from app.schemas.game import GameResponse


class RestoreSessionRequest(StrictRequestModel):
    """One-time reconnect credential used to rotate an anonymous session."""

    reconnect_token: str = Field(min_length=32, max_length=256)


class SessionIssuedResponse(BaseModel):
    """Fresh credentials plus the restored or newly joined room state."""

    game: GameResponse
    player_id: UUID
    session_token: str
    reconnect_token: str
