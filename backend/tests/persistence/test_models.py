"""Tests for the persisted TOMANAP domain graph."""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import CATEGORIES
from app.models import AnonymousSession, Game, Player, Round, Score, Submission
from app.models.enums import GameStatus
from tests.persistence.helpers import NOW, create_game, create_player, create_round


def _answers() -> dict[str, str]:
    return {
        "countries": "Polonia",
        "cities": "Ploiești",
        "brands": "Pagani",
        "activities": "Ping-Pong",
        "names": "Petru",
        "animals": "Pinguin",
        "plants": "Păpădie",
    }


async def test_complete_game_graph_can_be_persisted_and_queried(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    player = await create_player(session, game, is_host=True)

    anonymous_session = AnonymousSession(
        player_id=player.id,
        session_token_hash="a" * 64,
        reconnect_token_hash="b" * 64,
        expires_at=NOW + timedelta(hours=2),
        reconnect_expires_at=NOW + timedelta(days=7),
    )
    session.add(anonymous_session)

    round_record = await create_round(session, game, is_current=True)
    game.status = GameStatus.IN_PROGRESS

    submission = Submission(
        game_id=game.id,
        round_id=round_record.id,
        player_id=player.id,
        answers=_answers(),
        normalized_answers={key: value.casefold() for key, value in _answers().items()},
        submitted_at=NOW + timedelta(seconds=10),
        is_finalized=True,
        finalized_at=NOW + timedelta(seconds=10),
    )
    session.add(submission)
    session.add_all(
        Score(
            game_id=game.id,
            round_id=round_record.id,
            player_id=player.id,
            category=category,
            points=10,
            original_answer=_answers()[category.value],
            normalized_answer=_answers()[category.value].casefold(),
        )
        for category in CATEGORIES
    )
    await session.commit()

    loaded = await session.scalar(
        select(Game)
        .where(Game.id == game.id)
        .options(selectinload(Game.players), selectinload(Game.rounds))
    )
    assert loaded is not None
    assert loaded.players[0].is_host is True
    assert loaded.rounds[0].is_current is True
    assert [member.display_name for member in loaded.players] == ["Mihai"]
    assert [item.letter for item in loaded.rounds] == ["P"]
    assert await session.scalar(select(func.count(Score.id))) == 7


async def test_deleting_a_game_cascades_through_the_domain_graph(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    player = await create_player(session, game)
    round_record = await create_round(session, game)
    session.add(
        Submission(
            game_id=game.id,
            round_id=round_record.id,
            player_id=player.id,
            answers={},
            normalized_answers={},
        )
    )
    await session.commit()

    await session.delete(game)
    await session.commit()

    assert await session.scalar(select(func.count(Player.id))) == 0
    assert await session.scalar(select(func.count(Round.id))) == 0
    assert await session.scalar(select(func.count(Submission.id))) == 0


def test_anonymous_session_model_has_hashes_but_no_plaintext_tokens() -> None:
    column_names = set(AnonymousSession.__table__.columns.keys())

    assert "session_token_hash" in column_names
    assert "reconnect_token_hash" in column_names
    assert "session_token" not in column_names
    assert "reconnect_token" not in column_names
