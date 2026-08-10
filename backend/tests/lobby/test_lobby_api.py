"""End-to-end HTTP tests for anonymous sessions and lobbies."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import IdempotencyRecord

SESSION_HEADER = "X-TOMANAP-Session"


def _create_room(
    client: TestClient,
    *,
    display_name: str = "Mihai",
) -> dict[str, Any]:
    response = client.post(
        "/games",
        json={
            "display_name": display_name,
            "round_count": 5,
            "round_duration_seconds": 60,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _join_room(
    client: TestClient,
    room_code: str,
    display_name: str,
) -> dict[str, Any]:
    response = client.post(
        f"/games/{room_code}/join",
        json={"display_name": display_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_room_issues_host_tokens_and_public_state(
    lobby_client: TestClient,
) -> None:
    created = _create_room(lobby_client)

    game = created["game"]
    assert game["status"] == "lobby"
    assert game["round_count"] == 5
    assert game["round_duration_seconds"] == 60
    assert len(game["room_code"]) == 6
    assert game["room_code"] == game["room_code"].upper()
    assert created["session_token"] != created["reconnect_token"]
    assert len(created["session_token"]) >= 43
    assert game["players"] == [
        {
            "id": created["player_id"],
            "display_name": "Mihai",
            "seat_number": 1,
            "is_host": True,
            "is_ready": False,
            "is_connected": True,
        }
    ]

    public = lobby_client.get(f"/games/{game['room_code'].lower()}")
    assert public.status_code == 200
    assert public.json() == game


def test_join_rejects_normalized_duplicates_and_enforces_capacity(
    lobby_client: TestClient,
) -> None:
    created = _create_room(lobby_client)
    room_code = created["game"]["room_code"]

    duplicate = lobby_client.post(
        f"/games/{room_code}/join",
        json={"display_name": "  MÎHAI  "},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_display_name"

    joined = [
        _join_room(lobby_client, room_code, name)
        for name in ["Ana", "Radu", "Ioana", "Dan", "Elena"]
    ]
    assert [item["player_id"] for item in joined]
    assert [player["seat_number"] for player in joined[-1]["game"]["players"]] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]

    full = lobby_client.post(
        f"/games/{room_code}/join",
        json={"display_name": "Vlad"},
    )
    assert full.status_code == 409
    assert full.json()["error"]["code"] == "lobby_full"


def test_restore_rotates_both_tokens_and_invalidates_old_credentials(
    lobby_client: TestClient,
) -> None:
    created = _create_room(lobby_client)
    room_code = created["game"]["room_code"]

    restored_response = lobby_client.post(
        "/sessions/restore",
        json={"reconnect_token": created["reconnect_token"]},
    )
    assert restored_response.status_code == 200
    restored = restored_response.json()
    assert restored["player_id"] == created["player_id"]
    assert restored["session_token"] != created["session_token"]
    assert restored["reconnect_token"] != created["reconnect_token"]

    reused = lobby_client.post(
        "/sessions/restore",
        json={"reconnect_token": created["reconnect_token"]},
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "invalid_session"

    old_session = lobby_client.post(
        f"/games/{room_code}/ready",
        headers={SESSION_HEADER: created["session_token"]},
        json={"is_ready": True},
    )
    assert old_session.status_code == 401

    new_session = lobby_client.post(
        f"/games/{room_code}/ready",
        headers={SESSION_HEADER: restored["session_token"]},
        json={"is_ready": True},
    )
    assert new_session.status_code == 200


def test_host_controls_settings_and_start_requires_ready_players(
    lobby_client: TestClient,
) -> None:
    host = _create_room(lobby_client)
    room_code = host["game"]["room_code"]
    ana = _join_room(lobby_client, room_code, "Ana")

    non_host_settings = lobby_client.patch(
        f"/games/{room_code}/settings",
        headers={SESSION_HEADER: ana["session_token"]},
        json={"round_count": 3},
    )
    assert non_host_settings.status_code == 403

    premature = lobby_client.post(
        f"/games/{room_code}/start",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert premature.status_code == 409
    assert premature.json()["error"]["code"] == "invalid_state"

    ready = lobby_client.post(
        f"/games/{room_code}/ready",
        headers={SESSION_HEADER: ana["session_token"]},
        json={"is_ready": True},
    )
    assert ready.status_code == 200
    assert ready.json()["players"][1]["is_ready"] is True

    configured = lobby_client.patch(
        f"/games/{room_code}/settings",
        headers={SESSION_HEADER: host["session_token"]},
        json={"round_count": 3, "round_duration_seconds": 90},
    )
    assert configured.status_code == 200
    assert configured.json()["round_count"] == 3
    assert configured.json()["round_duration_seconds"] == 90

    started = lobby_client.post(
        f"/games/{room_code}/start",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    late_join = lobby_client.post(
        f"/games/{room_code}/join",
        json={"display_name": "Late"},
    )
    assert late_join.status_code == 409
    assert late_join.json()["error"]["code"] == "invalid_state"


def test_non_host_cannot_start_and_single_player_game_cannot_start(
    lobby_client: TestClient,
) -> None:
    host = _create_room(lobby_client)
    room_code = host["game"]["room_code"]

    alone = lobby_client.post(
        f"/games/{room_code}/start",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert alone.status_code == 409

    ana = _join_room(lobby_client, room_code, "Ana")
    forbidden = lobby_client.post(
        f"/games/{room_code}/start",
        headers={SESSION_HEADER: ana["session_token"]},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "capability_denied"


def test_game_start_replays_same_idempotent_response(
    lobby_client: TestClient,
) -> None:
    host = _create_room(lobby_client)
    room_code = host["game"]["room_code"]
    guest = _join_room(lobby_client, room_code, "Ana")
    assert (
        lobby_client.post(
            f"/games/{room_code}/ready",
            headers={SESSION_HEADER: guest["session_token"]},
            json={"is_ready": True},
        ).status_code
        == 200
    )
    headers = {
        SESSION_HEADER: host["session_token"],
        "Idempotency-Key": "start-game-request-0001",
    }

    first = lobby_client.post(f"/games/{room_code}/start", headers=headers)
    replay = lobby_client.post(f"/games/{room_code}/start", headers=headers)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert replay.headers["Idempotency-Replayed"] == "true"

    async def persisted_record() -> tuple[str, dict[str, object]]:
        async with lobby_client.app.state.database.session() as session:
            async with session.begin():
                record = await session.scalar(select(IdempotencyRecord))
                assert record is not None
                assert record.response_payload is not None
                return record.key_hash, dict(record.response_payload)

    assert lobby_client.portal is not None
    key_hash, response_payload = lobby_client.portal.call(persisted_record)
    assert len(key_hash) == 64
    assert key_hash != headers["Idempotency-Key"]
    assert response_payload == first.json()


def test_explicit_host_leave_revokes_session_and_transfers_host(
    lobby_client: TestClient,
) -> None:
    host = _create_room(lobby_client)
    room_code = host["game"]["room_code"]
    ana = _join_room(lobby_client, room_code, "Ana")
    _join_room(lobby_client, room_code, "Radu")

    left = lobby_client.post(
        f"/games/{room_code}/leave",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert left.status_code == 204

    public = lobby_client.get(f"/games/{room_code}")
    assert public.status_code == 200
    assert [player["display_name"] for player in public.json()["players"]] == [
        "Ana",
        "Radu",
    ]
    assert public.json()["players"][0]["is_host"] is True

    revoked = lobby_client.post(
        f"/games/{room_code}/ready",
        headers={SESSION_HEADER: host["session_token"]},
        json={"is_ready": True},
    )
    assert revoked.status_code == 401

    new_host_settings = lobby_client.patch(
        f"/games/{room_code}/settings",
        headers={SESSION_HEADER: ana["session_token"]},
        json={"round_count": 4},
    )
    assert new_host_settings.status_code == 200


def test_missing_or_invalid_session_is_unauthorized(
    lobby_client: TestClient,
) -> None:
    created = _create_room(lobby_client)
    room_code = created["game"]["room_code"]

    missing = lobby_client.post(
        f"/games/{room_code}/ready",
        json={"is_ready": True},
    )
    invalid = lobby_client.post(
        f"/games/{room_code}/ready",
        headers={SESSION_HEADER: "not-a-valid-token"},
        json={"is_ready": True},
    )
    oversized = lobby_client.post(
        f"/games/{room_code}/ready",
        headers={SESSION_HEADER: "a" * 257},
        json={"is_ready": True},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert oversized.status_code == 401
    assert missing.json()["error"]["code"] == "invalid_session"
    assert invalid.json()["error"]["code"] == "invalid_session"


def test_valid_session_cannot_mutate_a_different_room(
    lobby_client: TestClient,
) -> None:
    first = _create_room(lobby_client, display_name="Ana")
    second = _create_room(lobby_client, display_name="Radu")

    response = lobby_client.patch(
        f"/games/{second['game']['room_code']}/settings",
        headers={SESSION_HEADER: first["session_token"]},
        json={"round_count": 4},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "capability_denied"
