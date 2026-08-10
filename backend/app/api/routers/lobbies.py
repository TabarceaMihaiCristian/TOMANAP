"""Ready, unready, and explicit lobby-leave endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_database_session,
    get_outbox_dispatcher,
    get_request_settings,
    get_session_token,
)
from app.core.config import Settings
from app.schemas.game import GameResponse
from app.schemas.player import ReadyRequest
from app.services.game_lifecycle import LobbyService
from app.services.outbox import OutboxDispatcher

router = APIRouter(prefix="/games", tags=["lobby"])


@router.post("/{room_code}/ready", response_model=GameResponse)
async def set_ready(
    room_code: str,
    request: ReadyRequest,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> GameResponse:
    """Set the current anonymous player's lobby readiness."""
    snapshot = await LobbyService(session, settings).set_ready(
        room_code,
        session_token,
        is_ready=request.is_ready,
    )
    response = GameResponse.model_validate(snapshot)
    await dispatcher.dispatch_once()
    return response


@router.post("/{room_code}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_game(
    room_code: str,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> Response:
    """Leave explicitly, revoke the seat's sessions, and transfer host."""
    await LobbyService(session, settings).leave_game(
        room_code,
        session_token,
    )
    await dispatcher.dispatch_once()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
