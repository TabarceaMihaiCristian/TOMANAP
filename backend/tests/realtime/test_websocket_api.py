"""End-to-end tests for authenticated game WebSockets."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from starlette.websockets import WebSocketDisconnect

from app.models import OutboxEvent, RealtimeTicket
from app.utilities.datetime import utc_now

ORIGIN_HEADERS = {"Origin": "https://game.example.test"}


def _outbox_events(client: TestClient) -> list[OutboxEvent]:
    async def load() -> list[OutboxEvent]:
        async with client.app.state.database.session() as session:
            async with session.begin():
                statement = select(OutboxEvent).order_by(OutboxEvent.occurred_at)
                return list((await session.scalars(statement)).all())

    assert client.portal is not None
    return client.portal.call(load)


def _create_room(client: TestClient, display_name: str) -> dict[str, object]:
    response = client.post(
        "/games",
        json={
            "display_name": display_name,
            "round_count": 3,
            "round_duration_seconds": 60,
        },
    )
    assert response.status_code == 201
    return response.json()


def _issue_ticket(client: TestClient, created: dict[str, Any]) -> dict[str, str]:
    response = client.post(
        f"/games/{created['game']['room_code']}/realtime-ticket",
        headers={"X-TOMANAP-Session": created["session_token"]},
    )
    assert response.status_code == 200, response.text
    ticket = response.json()
    assert len(ticket["ticket"]) >= 43
    assert ticket["expires_at"] is not None
    return ticket


def test_websocket_uses_short_lived_ticket_without_putting_session_in_url(
    realtime_client: TestClient,
) -> None:
    created = _create_room(realtime_client, "Mihai")
    game = created["game"]
    issued = _issue_ticket(realtime_client, created)

    with realtime_client.websocket_connect(
        f"/ws/games/{game['room_code']}",
        subprotocols=["tomanap.ticket", issued["ticket"]],
        headers=ORIGIN_HEADERS.copy(),
    ) as websocket:
        message = websocket.receive_json()

        assert websocket.accepted_subprotocol == "tomanap.ticket"
        assert message["type"] == "connection.ready"
        assert message["room_code"] == game["room_code"]
        assert message["payload"]["player_id"] == created["player_id"]
        assert message["payload"]["game"] == game
        assert message["payload"]["resync_required"] is True
        assert message["payload"]["latest_event_id"] is not None
        assert "session_token" not in str(message)

        websocket.send_json({"type": "ping"})
        pong = websocket.receive_json()
        assert pong["type"] == "connection.pong"


@pytest.mark.parametrize(
    "protocols",
    [[], ["tomanap.ticket", "invalid-ticket"]],
)
def test_websocket_rejects_missing_or_invalid_ticket(
    realtime_client: TestClient,
    protocols: list[str],
) -> None:
    created = _create_room(realtime_client, "Mihai")

    with pytest.raises(WebSocketDisconnect) as error:
        with realtime_client.websocket_connect(
            f"/ws/games/{created['game']['room_code']}",
            subprotocols=protocols,
            headers=ORIGIN_HEADERS.copy(),
        ):
            pass

    assert error.value.code == 4401


def test_websocket_ticket_cannot_cross_rooms_or_be_replayed(
    realtime_client: TestClient,
) -> None:
    first = _create_room(realtime_client, "Mihai")
    second = _create_room(realtime_client, "Ana")
    issued = _issue_ticket(realtime_client, first)

    with pytest.raises(WebSocketDisconnect) as error:
        with realtime_client.websocket_connect(
            f"/ws/games/{second['game']['room_code']}",
            subprotocols=["tomanap.ticket", issued["ticket"]],
            headers=ORIGIN_HEADERS.copy(),
        ):
            pass

    assert error.value.code == 4401

    with realtime_client.websocket_connect(
        f"/ws/games/{first['game']['room_code']}",
        subprotocols=["tomanap.ticket", issued["ticket"]],
        headers=ORIGIN_HEADERS.copy(),
    ) as websocket:
        assert websocket.receive_json()["type"] == "connection.ready"

    with pytest.raises(WebSocketDisconnect) as replay_error:
        with realtime_client.websocket_connect(
            f"/ws/games/{first['game']['room_code']}",
            subprotocols=["tomanap.ticket", issued["ticket"]],
            headers=ORIGIN_HEADERS.copy(),
        ):
            pass
    assert replay_error.value.code == 4401


def test_websocket_rejects_legacy_session_token_handshake(
    realtime_client: TestClient,
) -> None:
    created = _create_room(realtime_client, "Mihai")

    with pytest.raises(WebSocketDisconnect) as error:
        with realtime_client.websocket_connect(
            f"/ws/games/{created['game']['room_code']}",
            subprotocols=["tomanap", created["session_token"]],
            headers=ORIGIN_HEADERS.copy(),
        ):
            pass

    assert error.value.code == 4401


def test_websocket_rejects_expired_ticket(
    realtime_client: TestClient,
) -> None:
    created = _create_room(realtime_client, "Mihai")
    issued = _issue_ticket(realtime_client, created)

    async def expire_ticket() -> None:
        async with realtime_client.app.state.database.session() as session:
            async with session.begin():
                await session.execute(
                    update(RealtimeTicket).values(
                        expires_at=utc_now() - timedelta(seconds=1)
                    )
                )

    assert realtime_client.portal is not None
    realtime_client.portal.call(expire_ticket)
    with pytest.raises(WebSocketDisconnect) as error:
        with realtime_client.websocket_connect(
            f"/ws/games/{created['game']['room_code']}",
            subprotocols=["tomanap.ticket", issued["ticket"]],
            headers=ORIGIN_HEADERS.copy(),
        ):
            pass

    assert error.value.code == 4401


@pytest.mark.parametrize("origin", [None, "https://attacker.example"])
def test_websocket_rejects_missing_or_untrusted_origin_without_consuming_ticket(
    realtime_client: TestClient,
    origin: str | None,
) -> None:
    created = _create_room(realtime_client, "Mihai")
    issued = _issue_ticket(realtime_client, created)
    headers = {} if origin is None else {"Origin": origin}

    with pytest.raises(WebSocketDisconnect) as error:
        with realtime_client.websocket_connect(
            f"/ws/games/{created['game']['room_code']}",
            subprotocols=["tomanap.ticket", issued["ticket"]],
            headers=headers,
        ):
            pass
    assert error.value.code == 4403

    with realtime_client.websocket_connect(
        f"/ws/games/{created['game']['room_code']}",
        subprotocols=["tomanap.ticket", issued["ticket"]],
        headers=ORIGIN_HEADERS.copy(),
    ) as websocket:
        assert websocket.receive_json()["type"] == "connection.ready"


def test_websocket_rejects_oversized_client_message(
    realtime_client: TestClient,
) -> None:
    created = _create_room(realtime_client, "Mihai")
    issued = _issue_ticket(realtime_client, created)

    with realtime_client.websocket_connect(
        f"/ws/games/{created['game']['room_code']}",
        subprotocols=["tomanap.ticket", issued["ticket"]],
        headers=ORIGIN_HEADERS.copy(),
    ) as websocket:
        assert websocket.receive_json()["type"] == "connection.ready"
        websocket.send_text("x" * 4097)
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_json()

    assert error.value.code == 1009


def test_committed_http_mutations_publish_token_free_room_events(
    publication_client: tuple[TestClient, Any],
) -> None:
    client, broker = publication_client
    host = _create_room(client, "Mihai")
    room_code = host["game"]["room_code"]
    guest_response = client.post(
        f"/games/{room_code}/join",
        json={"display_name": "Ana"},
    )
    assert guest_response.status_code == 201
    guest = guest_response.json()

    ready_response = client.post(
        f"/games/{room_code}/ready",
        headers={"X-TOMANAP-Session": guest["session_token"]},
        json={"is_ready": True},
    )
    assert ready_response.status_code == 200
    ready_event = broker.events[-1].as_message()
    assert ready_event["type"] == "lobby.updated"
    assert ready_event["payload"]["reason"] == "player_ready_changed"
    assert ready_event["payload"]["game"]["players"][1]["is_ready"] is True

    start_response = client.post(
        f"/games/{room_code}/start",
        headers={"X-TOMANAP-Session": host["session_token"]},
    )
    assert start_response.status_code == 200
    assert broker.events[-1].type == "game.started"

    current_response = client.get(
        f"/games/{room_code}/rounds/current",
        headers={"X-TOMANAP-Session": host["session_token"]},
    )
    round_state = current_response.json()["round"]
    answers = {
        category: f"{round_state['letter']}{index}"
        for index, category in enumerate(
            current_response.json()["categories"],
            start=1,
        )
    }
    draft_response = client.put(
        f"/rounds/{round_state['id']}/submission",
        headers={"X-TOMANAP-Session": host["session_token"]},
        json={"answers": answers},
    )
    assert draft_response.status_code == 200
    draft_event = broker.events[-1].as_message()
    assert draft_event["type"] == "submission.updated"
    assert draft_event["payload"] == {
        "round_id": round_state["id"],
        "player_id": host["player_id"],
        "revision": draft_response.json()["revision"],
        "is_finalized": False,
    }
    serialized_event = str(draft_event)
    assert host["session_token"] not in serialized_event
    serialized_payload = str(draft_event["payload"])
    assert all(answer not in serialized_payload for answer in answers.values())

    persisted_events = _outbox_events(client)
    persisted_draft = next(
        event for event in persisted_events if event.event_type == "submission.updated"
    )
    assert draft_event["event_id"] == str(persisted_draft.id)
    assert all(event.published_at is not None for event in persisted_events)
    assert {
        "lobby.created",
        "lobby.updated",
        "game.started",
        "submission.updated",
    } <= {event.event_type for event in persisted_events}


def test_failed_domain_transaction_does_not_stage_outbox_event(
    publication_client: tuple[TestClient, Any],
) -> None:
    client, _broker = publication_client
    host = _create_room(client, "Mihai")
    event_ids_before = {event.id for event in _outbox_events(client)}

    rejected = client.post(
        f"/games/{host['game']['room_code']}/start",
        headers={"X-TOMANAP-Session": host["session_token"]},
    )

    assert rejected.status_code == 409
    events_after = _outbox_events(client)
    assert {event.id for event in events_after} == event_ids_before
    assert all(event.event_type != "game.started" for event in events_after)


def test_session_restore_publishes_token_free_reconnect_event(
    publication_client: tuple[TestClient, Any],
) -> None:
    client, broker = publication_client
    created = _create_room(client, "Mihai")

    restored = client.post(
        "/sessions/restore",
        json={"reconnect_token": created["reconnect_token"]},
    )

    assert restored.status_code == 200
    event = broker.events[-1].as_message()
    assert event["type"] == "lobby.updated"
    assert event["payload"] == {
        "reason": "player_reconnected",
        "player_id": created["player_id"],
    }
    serialized = str(event)
    assert restored.json()["session_token"] not in serialized
    assert restored.json()["reconnect_token"] not in serialized
