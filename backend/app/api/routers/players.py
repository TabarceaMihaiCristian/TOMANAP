"""Anonymous room-join endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    enforce_entry_rate_limit,
    get_database_session,
    get_outbox_dispatcher,
    get_request_settings,
)
from app.core.config import Settings
from app.schemas.game import GameResponse
from app.schemas.player import JoinGameRequest
from app.schemas.session import SessionIssuedResponse
from app.services.game_lifecycle import LobbyService
from app.services.outbox import OutboxDispatcher

router = APIRouter(prefix="/games", tags=["players"])


@router.post(
    "/{room_code}/join",
    response_model=SessionIssuedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_entry_rate_limit)],
)
async def join_game(
    room_code: str,
    request: JoinGameRequest,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> SessionIssuedResponse:
    """Claim the next available anonymous seat in an active lobby."""
    result = await LobbyService(session, settings).join_game(
        room_code,
        request.display_name,
    )
    response = SessionIssuedResponse(
        game=GameResponse.model_validate(result.game),
        player_id=result.player_id,
        session_token=result.tokens.session_token,
        reconnect_token=result.tokens.reconnect_token,
    )
    await dispatcher.dispatch_once()
    return response
