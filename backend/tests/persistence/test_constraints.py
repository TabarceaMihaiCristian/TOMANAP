"""Tests for database-enforced TOMANAP invariants."""

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Category
from app.models import AnonymousSession, Game, Player, Round, Score, Submission
from tests.persistence.helpers import NOW, create_game, create_player, create_round


async def _expect_integrity_error(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_room_codes_are_unique(session: AsyncSession) -> None:
    session.add_all([Game(room_code="MUNTE7"), Game(room_code="MUNTE7")])

    await _expect_integrity_error(session)


async def test_room_codes_must_be_stored_in_canonical_uppercase(
    session: AsyncSession,
) -> None:
    session.add(Game(room_code="munte7"))

    await _expect_integrity_error(session)


async def test_normalized_names_are_unique_within_a_game(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    session.add_all(
        [
            Player(
                game_id=game.id,
                display_name="Ștefan",
                normalized_display_name="stefan",
                seat_number=1,
            ),
            Player(
                game_id=game.id,
                display_name="STEFAN",
                normalized_display_name="stefan",
                seat_number=2,
            ),
        ]
    )

    await _expect_integrity_error(session)


async def test_seats_are_unique_within_a_game(session: AsyncSession) -> None:
    game = await create_game(session)
    session.add_all(
        [
            Player(
                game_id=game.id,
                display_name="Ana",
                normalized_display_name="ana",
                seat_number=1,
            ),
            Player(
                game_id=game.id,
                display_name="Radu",
                normalized_display_name="radu",
                seat_number=1,
            ),
        ]
    )

    await _expect_integrity_error(session)


async def test_only_one_player_can_be_host_within_a_game(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    session.add_all(
        [
            Player(
                game_id=game.id,
                display_name="Ana",
                normalized_display_name="ana",
                seat_number=1,
                is_host=True,
            ),
            Player(
                game_id=game.id,
                display_name="Radu",
                normalized_display_name="radu",
                seat_number=2,
                is_host=True,
            ),
        ]
    )

    await _expect_integrity_error(session)


async def test_host_must_remain_an_active_member(session: AsyncSession) -> None:
    game = await create_game(session)
    session.add(
        Player(
            game_id=game.id,
            display_name="Ana",
            normalized_display_name="ana",
            seat_number=1,
            is_host=True,
            is_active=False,
        )
    )

    await _expect_integrity_error(session)


@pytest.mark.parametrize(
    "game",
    [
        Game(room_code="ABC123", round_count=0),
        Game(room_code="DEF456", round_count=27),
        Game(room_code="GHI789", round_duration_seconds=0),
    ],
)
async def test_game_settings_have_database_bounds(
    session: AsyncSession,
    game: Game,
) -> None:
    session.add(game)

    await _expect_integrity_error(session)


async def test_round_numbers_are_unique_within_a_game(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    session.add_all(
        [
            Round(game_id=game.id, sequence_number=1, letter="A"),
            Round(game_id=game.id, sequence_number=1, letter="B"),
        ]
    )

    await _expect_integrity_error(session)


async def test_burned_letters_cannot_repeat_within_a_game(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    session.add_all(
        [
            Round(game_id=game.id, sequence_number=1, letter="P"),
            Round(game_id=game.id, sequence_number=2, letter="P"),
        ]
    )

    await _expect_integrity_error(session)


async def test_only_one_round_can_be_current_within_a_game(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    session.add_all(
        [
            Round(
                game_id=game.id,
                sequence_number=1,
                letter="A",
                is_current=True,
            ),
            Round(
                game_id=game.id,
                sequence_number=2,
                letter="B",
                is_current=True,
            ),
        ]
    )

    await _expect_integrity_error(session)


async def test_completed_round_cannot_remain_current(session: AsyncSession) -> None:
    game = await create_game(session)
    session.add(
        Round(
            game_id=game.id,
            sequence_number=1,
            letter="A",
            status="COMPLETED",
            is_current=True,
        )
    )

    await _expect_integrity_error(session)


async def test_player_has_one_submission_per_round(session: AsyncSession) -> None:
    game = await create_game(session)
    player = await create_player(session, game)
    round_record = await create_round(session, game)
    session.add_all(
        [
            Submission(
                game_id=game.id,
                round_id=round_record.id,
                player_id=player.id,
                answers={},
                normalized_answers={},
            ),
            Submission(
                game_id=game.id,
                round_id=round_record.id,
                player_id=player.id,
                answers={},
                normalized_answers={},
            ),
        ]
    )

    await _expect_integrity_error(session)


async def test_category_score_can_be_stored_only_once(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    player = await create_player(session, game)
    round_record = await create_round(session, game)
    session.add_all(
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
                category=Category.COUNTRIES,
                points=10,
            ),
        ]
    )

    await _expect_integrity_error(session)


async def test_score_points_are_limited_to_game_values(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    player = await create_player(session, game)
    round_record = await create_round(session, game)
    session.add(
        Score(
            game_id=game.id,
            round_id=round_record.id,
            player_id=player.id,
            category=Category.COUNTRIES,
            points=7,
        )
    )

    await _expect_integrity_error(session)


async def test_submission_cannot_cross_game_boundaries(
    session: AsyncSession,
) -> None:
    first_game = await create_game(session, room_code="FIRST1")
    player = await create_player(session, first_game)
    second_game = await create_game(session, room_code="SECOND")
    other_round = await create_round(session, second_game)
    session.add(
        Submission(
            game_id=first_game.id,
            round_id=other_round.id,
            player_id=player.id,
            answers={},
            normalized_answers={},
        )
    )

    await _expect_integrity_error(session)


async def test_score_cannot_cross_game_boundaries(session: AsyncSession) -> None:
    first_game = await create_game(session, room_code="FIRST1")
    player = await create_player(session, first_game)
    second_game = await create_game(session, room_code="SECOND")
    other_round = await create_round(session, second_game)
    session.add(
        Score(
            game_id=first_game.id,
            round_id=other_round.id,
            player_id=player.id,
            category=Category.COUNTRIES,
            points=10,
        )
    )

    await _expect_integrity_error(session)


async def test_session_token_hashes_are_globally_unique(
    session: AsyncSession,
) -> None:
    game = await create_game(session)
    first = await create_player(session, game)
    second = await create_player(
        session,
        game,
        display_name="Ana",
        normalized_display_name="ana",
        seat_number=2,
    )
    session.add_all(
        [
            AnonymousSession(
                player_id=first.id,
                session_token_hash="a" * 64,
                reconnect_token_hash="b" * 64,
                expires_at=NOW + timedelta(hours=1),
                reconnect_expires_at=NOW + timedelta(days=1),
            ),
            AnonymousSession(
                player_id=second.id,
                session_token_hash="a" * 64,
                reconnect_token_hash="c" * 64,
                expires_at=NOW + timedelta(hours=1),
                reconnect_expires_at=NOW + timedelta(days=1),
            ),
        ]
    )

    await _expect_integrity_error(session)
