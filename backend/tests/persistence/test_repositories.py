"""Tests for repository reads and transaction-neutral writes."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Category
from app.models import AnonymousSession, Game, Player, Score, Submission
from app.repositories.games import GameRepository
from app.repositories.players import PlayerRepository
from app.repositories.rounds import RoundRepository
from app.repositories.scores import ScoreRepository
from app.repositories.sessions import SessionRepository
from app.repositories.submissions import SubmissionRepository
from tests.persistence.helpers import NOW, create_round


async def test_repositories_store_and_retrieve_the_domain_graph(
    session: AsyncSession,
) -> None:
    games = GameRepository(session)
    players = PlayerRepository(session)
    sessions = SessionRepository(session)
    rounds = RoundRepository(session)
    submissions = SubmissionRepository(session)
    scores = ScoreRepository(session)

    game = await games.add(Game(room_code="MUNTE7"))
    player = await players.add(
        Player(
            game_id=game.id,
            display_name="Mihai",
            normalized_display_name="mihai",
            seat_number=1,
        )
    )
    anonymous_session = await sessions.add(
        AnonymousSession(
            player_id=player.id,
            session_token_hash="a" * 64,
            reconnect_token_hash="b" * 64,
            expires_at=NOW + timedelta(hours=1),
            reconnect_expires_at=NOW + timedelta(days=7),
        )
    )
    round_record = await rounds.add(await create_round(session, game, is_current=True))
    submission = await submissions.add(
        Submission(
            game_id=game.id,
            round_id=round_record.id,
            player_id=player.id,
            answers={"countries": "Polonia"},
            normalized_answers={"countries": "polonia"},
        )
    )
    await scores.add_all(
        [
            Score(
                game_id=game.id,
                round_id=round_record.id,
                player_id=player.id,
                category=Category.COUNTRIES,
                points=10,
            ),
            Score(
                game_id=game.id,
                round_id=round_record.id,
                player_id=player.id,
                category=Category.CITIES,
                points=5,
            ),
        ]
    )

    assert await games.get_by_room_code("MUNTE7") == game
    assert await players.normalized_name_exists(game.id, "mihai") is True
    assert await players.list_for_game(game.id) == [player]
    assert await sessions.get_by_session_token_hash("a" * 64) == anonymous_session
    assert await sessions.get_by_reconnect_token_hash("b" * 64) == anonymous_session
    assert await rounds.get_current_for_game(game.id) == round_record
    assert await rounds.list_used_letters(game.id) == ["P"]
    assert await submissions.get_for_player_round(player.id, round_record.id) == (
        submission
    )
    assert len(await scores.get_round_scores(round_record.id)) == 2

    leaderboard = await scores.get_leaderboard(game.id)
    assert len(leaderboard) == 1
    assert leaderboard[0].player_id == player.id
    assert leaderboard[0].display_name == "Mihai"
    assert leaderboard[0].total_score == 15


async def test_repository_add_flushes_without_committing(
    session: AsyncSession,
) -> None:
    games = GameRepository(session)

    game = await games.add(Game(room_code="ABC123"))

    assert game.id is not None
    assert session.in_transaction() is True
