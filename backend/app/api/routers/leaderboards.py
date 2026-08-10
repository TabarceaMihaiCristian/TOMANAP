"""Authenticated cumulative leaderboard endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_database_session,
    get_request_settings,
    get_session_token,
)
from app.core.config import Settings
from app.schemas.leaderboard import LeaderboardResponse
from app.services.rounds import RoundService

router = APIRouter(prefix="/games", tags=["leaderboard"])


@router.get("/{room_code}/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    room_code: str,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> LeaderboardResponse:
    """Return cumulative active-player standings with deterministic ties."""
    leaderboard = await RoundService(session, settings).get_leaderboard(
        room_code,
        session_token,
    )
    return LeaderboardResponse.model_validate(
        leaderboard,
        from_attributes=True,
    )
