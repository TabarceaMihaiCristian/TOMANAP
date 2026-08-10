"""End-to-end tests for rounds, submissions, scoring, and completion."""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.constants import ALPHABET, CATEGORIES

SESSION_HEADER = "X-TOMANAP-Session"


def _start_game(
    client: TestClient,
    *,
    round_count: int = 2,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    host_response = client.post(
        "/games",
        json={
            "display_name": "Mihai",
            "round_count": round_count,
            "round_duration_seconds": 60,
        },
    )
    assert host_response.status_code == 201
    host = host_response.json()
    room_code = host["game"]["room_code"]

    guest_response = client.post(
        f"/games/{room_code}/join",
        json={"display_name": "Ana"},
    )
    assert guest_response.status_code == 201
    guest = guest_response.json()
    ready = client.post(
        f"/games/{room_code}/ready",
        headers={SESSION_HEADER: guest["session_token"]},
        json={"is_ready": True},
    )
    assert ready.status_code == 200
    started = client.post(
        f"/games/{room_code}/start",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert started.status_code == 200

    current_response = client.get(
        f"/games/{room_code}/rounds/current",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert current_response.status_code == 200, current_response.text
    return host, guest, current_response.json()


def _answers(letter: str, *, suffix: str = "") -> dict[str, str]:
    return {
        category.value: f"{letter}{index}{suffix}"
        for index, category in enumerate(CATEGORIES, start=1)
    }


def _submit_and_finalize(
    client: TestClient,
    round_id: str,
    session_token: str,
    answers: dict[str, str],
) -> dict[str, Any]:
    draft = client.put(
        f"/rounds/{round_id}/submission",
        headers={SESSION_HEADER: session_token},
        json={"answers": answers},
    )
    assert draft.status_code == 200, draft.text
    finalized = client.post(
        f"/rounds/{round_id}/submission/finalize",
        headers={SESSION_HEADER: session_token},
    )
    assert finalized.status_code == 200, finalized.text
    return finalized.json()


def test_start_creates_an_authoritative_first_round(
    gameplay_client: TestClient,
) -> None:
    host, _guest, current = _start_game(gameplay_client)

    round_state = current["round"]
    assert round_state["sequence_number"] == 1
    assert round_state["letter"] in ALPHABET
    assert round_state["status"] == "active"
    assert round_state["is_current"] is True
    assert round_state["starts_at"] is not None
    assert round_state["ends_at"] is not None
    assert current["categories"] == [category.value for category in CATEGORIES]
    assert current["submission"] is None

    unauthorized = gameplay_client.get(
        f"/games/{host['game']['room_code']}/rounds/current"
    )
    assert unauthorized.status_code == 401


def test_drafts_finalize_idempotently_and_score_normalized_duplicates(
    gameplay_client: TestClient,
) -> None:
    host, guest, current = _start_game(gameplay_client)
    round_id = current["round"]["id"]
    letter = current["round"]["letter"]
    answers = _answers(letter)

    first_draft = gameplay_client.put(
        f"/rounds/{round_id}/submission",
        headers={SESSION_HEADER: host["session_token"]},
        json={"answers": answers},
    )
    assert first_draft.status_code == 200
    edited = gameplay_client.put(
        f"/rounds/{round_id}/submission",
        headers={SESSION_HEADER: host["session_token"]},
        json={"answers": answers},
    )
    assert edited.status_code == 200
    assert edited.json()["revision"] > first_draft.json()["revision"]

    host_final = gameplay_client.post(
        f"/rounds/{round_id}/submission/finalize",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert host_final.status_code == 200
    assert host_final.json()["is_finalized"] is True

    immutable_draft = gameplay_client.put(
        f"/rounds/{round_id}/submission",
        headers={SESSION_HEADER: host["session_token"]},
        json={"answers": _answers(letter, suffix="changed")},
    )
    assert immutable_draft.status_code == 409

    _submit_and_finalize(
        gameplay_client,
        round_id,
        guest["session_token"],
        {key: value.upper() for key, value in answers.items()},
    )

    repeated = gameplay_client.post(
        f"/rounds/{round_id}/submission/finalize",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == host_final.json()["id"]

    room_code = host["game"]["room_code"]
    current_review = gameplay_client.get(
        f"/games/{room_code}/rounds/current",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert current_review.status_code == 200
    assert current_review.json()["round"]["status"] == "review"

    review = gameplay_client.get(
        f"/rounds/{round_id}/review",
        headers={SESSION_HEADER: guest["session_token"]},
    )
    assert review.status_code == 200
    assert [player["total_score"] for player in review.json()["players"]] == [
        35,
        35,
    ]
    assert all(
        answer["points"] == 5
        for player in review.json()["players"]
        for answer in player["answers"]
    )

    leaderboard = gameplay_client.get(
        f"/games/{room_code}/leaderboard",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert leaderboard.status_code == 200
    assert [entry["total_score"] for entry in leaderboard.json()["entries"]] == [
        35,
        35,
    ]


def test_gameplay_enforces_room_capabilities_and_host_only_advancement(
    gameplay_client: TestClient,
) -> None:
    host, guest, current = _start_game(gameplay_client, round_count=1)
    round_id = current["round"]["id"]

    outsider_response = gameplay_client.post(
        "/games",
        json={
            "display_name": "Outsider",
            "round_count": 1,
            "round_duration_seconds": 60,
        },
    )
    assert outsider_response.status_code == 201
    outsider = outsider_response.json()

    cross_room_submission = gameplay_client.put(
        f"/rounds/{round_id}/submission",
        headers={SESSION_HEADER: outsider["session_token"]},
        json={"answers": _answers(current["round"]["letter"])},
    )
    assert cross_room_submission.status_code == 403

    answers = _answers(current["round"]["letter"])
    _submit_and_finalize(
        gameplay_client,
        round_id,
        host["session_token"],
        answers,
    )
    _submit_and_finalize(
        gameplay_client,
        round_id,
        guest["session_token"],
        answers,
    )

    room_code = host["game"]["room_code"]
    non_host_advance = gameplay_client.post(
        f"/games/{room_code}/rounds/next",
        headers={SESSION_HEADER: guest["session_token"]},
    )
    assert non_host_advance.status_code == 403

    cross_room_review = gameplay_client.get(
        f"/rounds/{round_id}/review",
        headers={SESSION_HEADER: outsider["session_token"]},
    )
    assert cross_room_review.status_code == 403


def test_host_advances_to_an_unused_letter_then_completes_game(
    gameplay_client: TestClient,
) -> None:
    host, guest, current = _start_game(gameplay_client, round_count=2)
    first_round = current["round"]
    answers = _answers(first_round["letter"])
    _submit_and_finalize(
        gameplay_client,
        first_round["id"],
        host["session_token"],
        answers,
    )
    _submit_and_finalize(
        gameplay_client,
        first_round["id"],
        guest["session_token"],
        answers,
    )

    room_code = host["game"]["room_code"]
    advanced = gameplay_client.post(
        f"/games/{room_code}/rounds/next",
        headers={
            SESSION_HEADER: host["session_token"],
            "Idempotency-Key": "advance-round-request-0001",
        },
    )
    assert advanced.status_code == 200, advanced.text
    second_round = advanced.json()["current_round"]
    assert advanced.json()["game_status"] == "in_progress"
    assert second_round["sequence_number"] == 2
    assert second_round["letter"] != first_round["letter"]
    replayed_advance = gameplay_client.post(
        f"/games/{room_code}/rounds/next",
        headers={
            SESSION_HEADER: host["session_token"],
            "Idempotency-Key": "advance-round-request-0001",
        },
    )
    assert replayed_advance.status_code == 200
    assert replayed_advance.json() == advanced.json()
    assert replayed_advance.headers["Idempotency-Replayed"] == "true"

    second_answers = _answers(second_round["letter"])
    _submit_and_finalize(
        gameplay_client,
        second_round["id"],
        host["session_token"],
        second_answers,
    )
    _submit_and_finalize(
        gameplay_client,
        second_round["id"],
        guest["session_token"],
        second_answers,
    )

    completed = gameplay_client.post(
        f"/games/{room_code}/rounds/next",
        headers={
            SESSION_HEADER: host["session_token"],
            "Idempotency-Key": "advance-round-request-0002",
        },
    )
    assert completed.status_code == 200
    assert completed.json() == {
        "game_status": "completed",
        "current_round": None,
    }
    replayed_completion = gameplay_client.post(
        f"/games/{room_code}/rounds/next",
        headers={
            SESSION_HEADER: host["session_token"],
            "Idempotency-Key": "advance-round-request-0002",
        },
    )
    assert replayed_completion.status_code == 200
    assert replayed_completion.json() == completed.json()
    assert replayed_completion.headers["Idempotency-Replayed"] == "true"


def test_authoritative_deadline_closes_and_scores_missing_answers_zero(
    gameplay_client: TestClient,
    settings: Settings,
) -> None:
    host, _guest, current = _start_game(gameplay_client, round_count=1)
    round_id = current["round"]["id"]
    database_path = Path(settings.database_url.removeprefix("sqlite+aiosqlite:///"))
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            "UPDATE rounds SET starts_at = ?, ends_at = ?",
            (
                "1999-12-31 23:59:00.000000",
                "2000-01-01 00:00:00.000000",
            ),
        )
        connection.commit()

    late_submission = gameplay_client.put(
        f"/rounds/{round_id}/submission",
        headers={SESSION_HEADER: host["session_token"]},
        json={"answers": _answers(current["round"]["letter"])},
    )
    assert late_submission.status_code == 409

    closed = gameplay_client.get(
        f"/games/{host['game']['room_code']}/rounds/current",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert closed.status_code == 200
    assert closed.json()["round"]["status"] == "review"
    closed_again = gameplay_client.get(
        f"/games/{host['game']['room_code']}/rounds/current",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert closed_again.status_code == 200
    assert closed_again.json()["round"]["status"] == "review"

    review = gameplay_client.get(
        f"/rounds/{round_id}/review",
        headers={SESSION_HEADER: host["session_token"]},
    )
    assert review.status_code == 200
    assert [player["total_score"] for player in review.json()["players"]] == [0, 0]
    assert all(
        answer["points"] == 0
        for player in review.json()["players"]
        for answer in player["answers"]
    )
