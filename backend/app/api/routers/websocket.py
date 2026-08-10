"""Authenticated realtime game WebSocket endpoint."""

import asyncio
import json
import time
from contextlib import suppress
from uuid import uuid4

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from app.api.dependencies import get_session_token
from app.core.exceptions import InvalidSessionError
from app.repositories.outbox import OutboxRepository
from app.schemas.game import GameResponse
from app.schemas.realtime import RealtimeTicketResponse
from app.services.game_lifecycle import LobbyService
from app.services.realtime import RealtimeEvent
from app.services.realtime_connections import (
    RealtimeCapacityError,
    RealtimeDrainingError,
)
from app.services.realtime_tickets import RealtimeTicketService
from app.utilities.datetime import utc_now

router = APIRouter(tags=["realtime"])
WEBSOCKET_PROTOCOL = "tomanap.ticket"


def _ticket_from_protocol(websocket: WebSocket) -> str:
    protocols = websocket.scope.get("subprotocols", [])
    if (
        len(protocols) != 2
        or protocols[0] != WEBSOCKET_PROTOCOL
        or not protocols[1]
        or len(protocols[1]) > 256
    ):
        raise InvalidSessionError()
    return protocols[1]


def _has_trusted_origin(websocket: WebSocket) -> bool:
    """Require an exact browser origin allowlist match before using a ticket."""
    origin = websocket.headers.get("origin")
    return origin is not None and origin in websocket.app.state.settings.cors_origins


@router.post(
    "/games/{room_code}/realtime-ticket",
    response_model=RealtimeTicketResponse,
)
async def issue_realtime_ticket(
    websocket_request: Request,
    room_code: str,
) -> RealtimeTicketResponse:
    """Exchange an authenticated session capability for a one-time ticket."""
    session_token = get_session_token(websocket_request)
    async with websocket_request.app.state.database.session() as session:
        issued = await RealtimeTicketService(
            session,
            websocket_request.app.state.settings,
        ).issue(room_code, session_token)
    return RealtimeTicketResponse(
        ticket=issued.ticket,
        expires_at=issued.expires_at,
    )


async def _cancel(task: asyncio.Task[object]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def _control_event(room_code: str, event_type: str) -> dict[str, object]:
    return RealtimeEvent(
        id=uuid4(),
        sequence=0,
        type=event_type,
        room_code=room_code,
        occurred_at=utc_now(),
        payload={},
    ).as_message()


@router.websocket("/ws/games/{room_code}")
async def game_websocket(websocket: WebSocket, room_code: str) -> None:
    """Stream token-free room events after capability authentication."""
    if not _has_trusted_origin(websocket):
        await websocket.close(code=4403)
        return
    try:
        plaintext_ticket = _ticket_from_protocol(websocket)
    except InvalidSessionError:
        await websocket.close(code=4401)
        return

    settings = websocket.app.state.settings
    database = websocket.app.state.database
    normalized_room_code = room_code.strip().upper()
    try:
        async with database.session() as session:
            consumed = await RealtimeTicketService(
                session,
                settings,
            ).consume(normalized_room_code, plaintext_ticket)
            snapshot = await LobbyService(session, settings).get_state_by_id(
                consumed.game.id
            )
            player_id = consumed.player.id
            latest_event = await OutboxRepository(session).get_latest_for_room(
                normalized_room_code
            )
            latest_event_id = str(latest_event.id) if latest_event is not None else None
    except InvalidSessionError:
        await websocket.close(code=4401)
        return

    broker = websocket.app.state.realtime_broker
    connection_manager = websocket.app.state.realtime_connections
    try:
        async with connection_manager.register(normalized_room_code, player_id):
            async with broker.subscribe(normalized_room_code) as queue:
                await websocket.accept(subprotocol=WEBSOCKET_PROTOCOL)
                ready = RealtimeEvent(
                    id=uuid4(),
                    sequence=0,
                    type="connection.ready",
                    room_code=normalized_room_code,
                    occurred_at=utc_now(),
                    payload={
                        "player_id": str(player_id),
                        "game": GameResponse.model_validate(snapshot).model_dump(
                            mode="json"
                        ),
                        "resync_required": True,
                        "latest_event_id": latest_event_id,
                    },
                )
                await websocket.send_json(ready.as_message())
                last_activity = time.monotonic()

                while True:
                    event_task = asyncio.create_task(queue.get())
                    receive_task = asyncio.create_task(websocket.receive())
                    drain_task = asyncio.create_task(
                        connection_manager.wait_for_drain()
                    )
                    try:
                        done, _pending = await asyncio.wait(
                            {event_task, receive_task, drain_task},
                            timeout=settings.realtime_heartbeat_seconds,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if not done:
                            if (
                                time.monotonic() - last_activity
                                >= settings.realtime_idle_timeout_seconds
                            ):
                                await websocket.close(code=4408)
                                return
                            await websocket.send_json(
                                _control_event(
                                    normalized_room_code,
                                    "connection.ping",
                                )
                            )
                            continue
                        if drain_task in done:
                            await websocket.close(code=1012)
                            return
                        if receive_task in done:
                            message = receive_task.result()
                            if message["type"] == "websocket.disconnect":
                                return
                            last_activity = time.monotonic()
                            raw_text = message.get("text")
                            if raw_text is None:
                                await websocket.close(code=4400)
                                return
                            if (
                                len(raw_text.encode("utf-8"))
                                > settings.realtime_max_message_bytes
                            ):
                                await websocket.close(code=1009)
                                return
                            try:
                                client_message = json.loads(raw_text)
                            except (json.JSONDecodeError, TypeError):
                                await websocket.close(code=4400)
                                return
                            if not isinstance(client_message, dict):
                                await websocket.close(code=4400)
                                return
                            message_type = client_message.get("type")
                            if message_type == "ping":
                                await websocket.send_json(
                                    _control_event(
                                        normalized_room_code,
                                        "connection.pong",
                                    )
                                )
                            elif message_type != "pong":
                                await websocket.close(code=4400)
                                return
                        if event_task in done:
                            await websocket.send_json(event_task.result().as_message())
                    except WebSocketDisconnect:
                        return
                    finally:
                        if not event_task.done():
                            await _cancel(event_task)
                        if not receive_task.done():
                            await _cancel(receive_task)
                        if not drain_task.done():
                            await _cancel(drain_task)
    except RealtimeDrainingError:
        await websocket.close(code=1012)
    except RealtimeCapacityError:
        await websocket.close(code=4429)
