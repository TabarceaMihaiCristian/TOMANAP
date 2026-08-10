"""Game creation, public state, host settings, and start endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    enforce_entry_rate_limit,
    get_database_session,
    get_outbox_dispatcher,
    get_request_settings,
    get_session_token,
)
from app.core.config import Settings
from app.schemas.game import (
    CreateGameRequest,
    GameResponse,
    UpdateGameSettingsRequest,
)
from app.schemas.session import SessionIssuedResponse
from app.services.game_lifecycle import LobbyService
from app.services.outbox import OutboxDispatcher

router = APIRouter(prefix="/games", tags=["games"])


@router.post(
    "",
    response_model=SessionIssuedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_entry_rate_limit)],
)
async def create_game(
    request: CreateGameRequest,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> SessionIssuedResponse:
    """Create a room and issue its host's anonymous credentials."""
    result = await LobbyService(session, settings).create_game(
        request.display_name,
        round_count=request.round_count,
        round_duration_seconds=request.round_duration_seconds,
    )
    response = SessionIssuedResponse(
        game=GameResponse.model_validate(result.game),
        player_id=result.player_id,
        session_token=result.tokens.session_token,
        reconnect_token=result.tokens.reconnect_token,
    )
    await dispatcher.dispatch_once()
    return response


@router.get("/{room_code}", response_model=GameResponse)
async def get_game(
    room_code: str,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> GameResponse:
    """Return public room state without exposing anonymous credentials."""
    snapshot = await LobbyService(session, settings).get_public_state(room_code)
    return GameResponse.model_validate(snapshot)


@router.patch("/{room_code}/settings", response_model=GameResponse)
async def update_game_settings(
    room_code: str,
    request: UpdateGameSettingsRequest,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> GameResponse:
    """Allow only the active host to update lobby settings."""
    snapshot = await LobbyService(session, settings).update_settings(
        room_code,
        session_token,
        round_count=request.round_count,
        round_duration_seconds=request.round_duration_seconds,
    )
    response = GameResponse.model_validate(snapshot)
    await dispatcher.dispatch_once()
    return response


@router.post("/{room_code}/start", response_model=GameResponse)
async def start_game(
    room_code: str,
    response_headers: Response,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
        ),
    ] = None,
) -> GameResponse:
    """Validate lobby readiness and transition the game to in progress."""
    command = await LobbyService(session, settings).start_game(
        room_code,
        session_token,
        idempotency_key=idempotency_key,
    )
    response = GameResponse.model_validate(command.game)
    if command.replayed:
        response_headers.headers["Idempotency-Replayed"] = "true"
    await dispatcher.dispatch_once()
    return response
