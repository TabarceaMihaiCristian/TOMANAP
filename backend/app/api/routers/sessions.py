"""Anonymous reconnect-token restoration endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    enforce_entry_rate_limit,
    get_database_session,
    get_outbox_dispatcher,
    get_request_settings,
)
from app.core.config import Settings
from app.schemas.game import GameResponse
from app.schemas.session import RestoreSessionRequest, SessionIssuedResponse
from app.services.game_lifecycle import LobbyService
from app.services.outbox import OutboxDispatcher
from app.services.sessions import AnonymousSessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "/restore",
    response_model=SessionIssuedResponse,
    dependencies=[Depends(enforce_entry_rate_limit)],
)
async def restore_session(
    request: RestoreSessionRequest,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> SessionIssuedResponse:
    """Rotate both credentials and restore the same active player seat."""
    restored = await AnonymousSessionService(session, settings).restore(
        request.reconnect_token
    )
    game = await LobbyService(session, settings).get_state_by_id(
        restored.context.game.id
    )
    response = SessionIssuedResponse(
        game=GameResponse.model_validate(game),
        player_id=restored.context.player.id,
        session_token=restored.tokens.session_token,
        reconnect_token=restored.tokens.reconnect_token,
    )
    await dispatcher.dispatch_once()
    return response
