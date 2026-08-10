"""Authoritative round, submission, scoring, review, and advance service."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import CATEGORIES, Category
from app.core.exceptions import (
    CapabilityDeniedError,
    InvalidStateError,
    ResourceNotFoundError,
)
from app.models import Game, Player, Round, Score, Submission
from app.models.enums import GameStatus, RoundStatus
from app.repositories.games import GameRepository
from app.repositories.players import PlayerRepository
from app.repositories.rounds import RoundRepository
from app.repositories.scores import ScoreRepository
from app.repositories.submissions import SubmissionRepository
from app.services.event_outbox import EventOutbox
from app.services.idempotency import IdempotencyService
from app.services.letters import select_unused_letter
from app.services.scoring import ScoringSubmission, score_round
from app.services.sessions import AnonymousSessionService
from app.utilities.datetime import as_utc, utc_now
from app.utilities.text import clean_answer, normalize_answer


@dataclass(frozen=True, slots=True)
class CurrentRoundResult:
    """Current round and the requesting player's private draft."""

    round: Round
    submission: Submission | None


@dataclass(frozen=True, slots=True)
class SubmissionMutationResult:
    """Persisted private submission plus its public event destination."""

    submission: Submission
    room_code: str


@dataclass(frozen=True, slots=True)
class ReviewAnswer:
    """Auditable per-category result used by review responses."""

    category: Category
    original_answer: str
    normalized_answer: str
    points: int
    validation_code: str | None


@dataclass(frozen=True, slots=True)
class PlayerReview:
    """One player's ordered round result."""

    player_id: UUID
    display_name: str
    total_score: int
    answers: tuple[ReviewAnswer, ...]


@dataclass(frozen=True, slots=True)
class RoundReview:
    """Complete scored review for one round."""

    round_id: UUID
    letter: str
    status: RoundStatus
    players: tuple[PlayerReview, ...]


@dataclass(frozen=True, slots=True)
class AdvanceResult:
    """Next active round or final game completion."""

    game_status: GameStatus
    current_round: Round | None


@dataclass(frozen=True, slots=True)
class AdvanceCommandResult:
    """Live or replayed host-advance response."""

    value: AdvanceResult | dict[str, object]
    replayed: bool


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    """Ranked cumulative player total."""

    rank: int
    player_id: UUID
    display_name: str
    total_score: int


@dataclass(frozen=True, slots=True)
class GameLeaderboard:
    """Cumulative standings for one game."""

    game_id: UUID
    entries: tuple[LeaderboardEntry, ...]


@dataclass(frozen=True, slots=True)
class DeadlineClosure:
    """System-authorized closure safe to publish after transaction commit."""

    round_id: UUID
    room_code: str


class RoundService:
    """Coordinate all authoritative gameplay state under row locks."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.games = GameRepository(session)
        self.players = PlayerRepository(session)
        self.rounds = RoundRepository(session)
        self.submissions = SubmissionRepository(session)
        self.scores = ScoreRepository(session)
        self.anonymous_sessions = AnonymousSessionService(session, settings)
        self.outbox = EventOutbox(session)
        self.idempotency = IdempotencyService(session, settings)

    async def _authorize(self, game: Game, session_token: str) -> Player:
        context = await self.anonymous_sessions.authenticate(session_token)
        if context.game.id != game.id:
            raise CapabilityDeniedError("Session does not belong to this game")
        return context.player

    @staticmethod
    def _require_host(player: Player) -> None:
        if not player.is_host:
            raise CapabilityDeniedError("Only the host can advance rounds")

    @staticmethod
    def _round_event_payload(round_record: Round) -> dict[str, object]:
        """Project only the public round fields into a durable event."""
        return {
            "id": str(round_record.id),
            "sequence_number": round_record.sequence_number,
            "letter": round_record.letter,
            "status": round_record.status.value,
            "is_current": round_record.is_current,
            "starts_at": round_record.starts_at,
            "ends_at": round_record.ends_at,
        }

    async def _locked_round_context(
        self,
        round_id: UUID,
        session_token: str,
    ) -> tuple[Game, Round, Player]:
        hint = await self.rounds.get_by_id(round_id)
        if hint is None:
            raise ResourceNotFoundError("Round not found")
        game = await self.games.lock_by_id(hint.game_id)
        if game is None:
            raise ResourceNotFoundError("Game not found")
        round_record = await self.rounds.lock_by_id(round_id)
        if round_record is None:
            raise ResourceNotFoundError("Round not found")
        player = await self._authorize(game, session_token)
        return game, round_record, player

    @staticmethod
    def _deadline_reached(round_record: Round, now: datetime) -> bool:
        if round_record.ends_at is None:
            raise InvalidStateError("Active round has no authoritative deadline")
        return now >= as_utc(round_record.ends_at)

    async def _all_active_players_finalized(
        self,
        game: Game,
        round_record: Round,
    ) -> bool:
        active_ids = {player.id for player in await self.players.list_for_game(game.id)}
        finalized_ids = {
            submission.player_id
            for submission in await self.submissions.list_for_round(round_record.id)
            if submission.is_finalized
        }
        return bool(active_ids) and active_ids <= finalized_ids

    async def _close_round(
        self,
        game: Game,
        round_record: Round,
        *,
        closed_at: datetime,
        reason: str,
    ) -> None:
        """Score exactly once; caller must hold the game and round row locks."""
        if round_record.scored_at is not None:
            return
        if round_record.status is not RoundStatus.ACTIVE:
            raise InvalidStateError("Only an active round can be scored")
        if round_record.ends_at is None:
            raise InvalidStateError("Round has no authoritative deadline")

        players = await self.players.list_for_game(game.id)
        submissions = {
            submission.player_id: submission
            for submission in await self.submissions.list_for_round(round_record.id)
        }
        fallback_time = as_utc(round_record.starts_at or closed_at)
        scoring_input = [
            ScoringSubmission(
                player_id=str(player.id),
                answers=(
                    submissions[player.id].answers if player.id in submissions else {}
                ),
                submitted_at=(
                    as_utc(submissions[player.id].submitted_at)
                    if player.id in submissions
                    and submissions[player.id].submitted_at is not None
                    else fallback_time
                ),
            )
            for player in players
        ]
        result = score_round(
            scoring_input,
            selected_letter=round_record.letter,
            ends_at=as_utc(round_record.ends_at),
        )

        player_by_text_id = {str(player.id): player for player in players}
        score_rows: list[Score] = []
        for player_id, player_score in result.players.items():
            player = player_by_text_id[player_id]
            player.cumulative_score += player_score.total
            score_rows.extend(
                Score(
                    game_id=game.id,
                    round_id=round_record.id,
                    player_id=player.id,
                    category=category,
                    points=scored_answer.points,
                    original_answer=scored_answer.original,
                    normalized_answer=scored_answer.normalized,
                    validation_code=(
                        scored_answer.validation_code.value
                        if scored_answer.validation_code is not None
                        else None
                    ),
                )
                for category, scored_answer in player_score.answers.items()
            )
        await self.scores.add_all(score_rows)
        round_record.status = RoundStatus.REVIEW
        round_record.finalized_at = closed_at
        round_record.scored_at = closed_at
        await self.outbox.stage(
            game.room_code,
            "round.closed",
            {"round_id": str(round_record.id), "reason": reason},
            occurred_at=closed_at,
        )
        await self.session.flush()

    async def _close_if_due(
        self,
        game: Game,
        round_record: Round,
        *,
        now: datetime,
    ) -> bool:
        if round_record.status is RoundStatus.ACTIVE and self._deadline_reached(
            round_record,
            now,
        ):
            await self._close_round(
                game,
                round_record,
                closed_at=now,
                reason="deadline_reached",
            )
            return True
        return False

    async def close_due_round(
        self,
        round_id: UUID,
        *,
        now: datetime | None = None,
    ) -> DeadlineClosure | None:
        """Close one expired round through the same idempotent scoring path."""
        checked_at = now or utc_now()
        closure: DeadlineClosure | None = None
        async with self.session.begin():
            hint = await self.rounds.get_by_id(round_id)
            if hint is None:
                return None
            game = await self.games.lock_by_id(hint.game_id)
            if game is None:
                return None
            round_record = await self.rounds.lock_by_id(round_id)
            if (
                round_record is not None
                and round_record.status is RoundStatus.ACTIVE
                and round_record.scored_at is None
                and self._deadline_reached(round_record, checked_at)
            ):
                await self._close_round(
                    game,
                    round_record,
                    closed_at=checked_at,
                    reason="deadline_reached",
                )
                closure = DeadlineClosure(round_record.id, game.room_code)
        return closure

    async def get_current(
        self,
        room_code: str,
        session_token: str,
        *,
        now: datetime | None = None,
    ) -> CurrentRoundResult:
        checked_at = now or utc_now()
        async with self.session.begin():
            game = await self.games.lock_by_room_code(room_code)
            if game is None:
                raise ResourceNotFoundError("Game not found")
            player = await self._authorize(game, session_token)
            round_record = await self.rounds.lock_current_for_game(game.id)
            if round_record is None:
                raise ResourceNotFoundError("Current round not found")
            await self._close_if_due(game, round_record, now=checked_at)
            submission = await self.submissions.get_for_player_round(
                player.id,
                round_record.id,
            )
        return CurrentRoundResult(round_record, submission)

    async def upsert_submission(
        self,
        round_id: UUID,
        session_token: str,
        answers: dict[str, str],
        *,
        now: datetime | None = None,
    ) -> SubmissionMutationResult:
        checked_at = now or utc_now()
        closed_by_deadline = False
        submission: Submission | None = None
        async with self.session.begin():
            game, round_record, player = await self._locked_round_context(
                round_id,
                session_token,
            )
            closed_by_deadline = await self._close_if_due(
                game,
                round_record,
                now=checked_at,
            )
            if not closed_by_deadline:
                if round_record.status is not RoundStatus.ACTIVE:
                    raise InvalidStateError("Round is not accepting submissions")
                submission = await self.submissions.lock_for_player_round(
                    player.id,
                    round_record.id,
                )
                if submission is not None and submission.is_finalized:
                    raise InvalidStateError("Submission is already finalized")
                cleaned = {
                    category.value: clean_answer(answers.get(category.value, ""))
                    for category in CATEGORIES
                }
                normalized = {
                    category: normalize_answer(answer)
                    for category, answer in cleaned.items()
                }
                if submission is None:
                    submission = await self.submissions.add(
                        Submission(
                            game_id=game.id,
                            round_id=round_record.id,
                            player_id=player.id,
                            answers=cleaned,
                            normalized_answers=normalized,
                            submitted_at=checked_at,
                        )
                    )
                else:
                    submission.answers = cleaned
                    submission.normalized_answers = normalized
                    submission.submitted_at = checked_at
                    await self.session.flush()
                await self.outbox.stage(
                    game.room_code,
                    "submission.updated",
                    {
                        "round_id": str(round_record.id),
                        "player_id": str(player.id),
                        "revision": submission.revision,
                        "is_finalized": submission.is_finalized,
                    },
                    occurred_at=checked_at,
                )
        if closed_by_deadline:
            raise InvalidStateError("Round deadline has passed")
        if submission is None:
            raise RuntimeError("Submission was not persisted")
        return SubmissionMutationResult(submission, game.room_code)

    async def finalize_submission(
        self,
        round_id: UUID,
        session_token: str,
        *,
        now: datetime | None = None,
    ) -> SubmissionMutationResult:
        checked_at = now or utc_now()
        rejected_after_close = False
        submission: Submission | None = None
        async with self.session.begin():
            game, round_record, player = await self._locked_round_context(
                round_id,
                session_token,
            )
            submission = await self.submissions.lock_for_player_round(
                player.id,
                round_record.id,
            )
            if round_record.status in {RoundStatus.REVIEW, RoundStatus.COMPLETED}:
                if submission is None or not submission.is_finalized:
                    raise InvalidStateError("Round is already closed")
            else:
                closed_by_deadline = await self._close_if_due(
                    game,
                    round_record,
                    now=checked_at,
                )
                if closed_by_deadline:
                    rejected_after_close = (
                        submission is None or not submission.is_finalized
                    )
                elif round_record.status is not RoundStatus.ACTIVE:
                    raise InvalidStateError("Round is not accepting submissions")
                elif submission is None:
                    empty_answers = {category.value: "" for category in CATEGORIES}
                    submission = await self.submissions.add(
                        Submission(
                            game_id=game.id,
                            round_id=round_record.id,
                            player_id=player.id,
                            answers=empty_answers,
                            normalized_answers=empty_answers.copy(),
                            submitted_at=checked_at,
                            is_finalized=True,
                            finalized_at=checked_at,
                        )
                    )
                elif not submission.is_finalized:
                    submission.is_finalized = True
                    submission.finalized_at = checked_at
                    await self.session.flush()

                if not closed_by_deadline and submission is not None:
                    await self.outbox.stage(
                        game.room_code,
                        "submission.finalized",
                        {
                            "round_id": str(round_record.id),
                            "player_id": str(player.id),
                            "revision": submission.revision,
                            "is_finalized": submission.is_finalized,
                        },
                        occurred_at=checked_at,
                    )

                if not closed_by_deadline and await self._all_active_players_finalized(
                    game, round_record
                ):
                    await self._close_round(
                        game,
                        round_record,
                        closed_at=checked_at,
                        reason="all_players_finalized",
                    )
        if rejected_after_close:
            raise InvalidStateError("Round deadline has passed")
        if submission is None:
            raise InvalidStateError("No finalized submission exists")
        return SubmissionMutationResult(submission, game.room_code)

    async def get_review(
        self,
        round_id: UUID,
        session_token: str,
        *,
        now: datetime | None = None,
    ) -> RoundReview:
        checked_at = now or utc_now()
        async with self.session.begin():
            game, round_record, _player = await self._locked_round_context(
                round_id,
                session_token,
            )
            await self._close_if_due(game, round_record, now=checked_at)
            if round_record.status not in {
                RoundStatus.REVIEW,
                RoundStatus.COMPLETED,
            }:
                raise InvalidStateError("Round review is not ready")

            players = await self.players.list_for_game(game.id)
            score_rows = await self.scores.get_round_scores(round_record.id)
            by_player: dict[UUID, dict[Category, Score]] = {}
            for score in score_rows:
                by_player.setdefault(score.player_id, {})[score.category] = score
            player_reviews = tuple(
                PlayerReview(
                    player_id=player.id,
                    display_name=player.display_name,
                    total_score=sum(
                        score.points for score in by_player.get(player.id, {}).values()
                    ),
                    answers=tuple(
                        ReviewAnswer(
                            category=category,
                            original_answer=by_player[player.id][
                                category
                            ].original_answer,
                            normalized_answer=by_player[player.id][
                                category
                            ].normalized_answer,
                            points=by_player[player.id][category].points,
                            validation_code=by_player[player.id][
                                category
                            ].validation_code,
                        )
                        for category in CATEGORIES
                    ),
                )
                for player in players
            )
        return RoundReview(
            round_id=round_record.id,
            letter=round_record.letter,
            status=round_record.status,
            players=player_reviews,
        )

    async def advance(
        self,
        room_code: str,
        session_token: str,
        *,
        now: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> AdvanceCommandResult:
        checked_at = now or utc_now()
        recovered_deadline = False
        result: AdvanceResult | None = None
        async with self.session.begin():
            game = await self.games.lock_by_room_code(room_code)
            if game is None:
                raise ResourceNotFoundError("Game not found")
            host = await self._authorize(game, session_token)
            self._require_host(host)
            idempotency = await self.idempotency.begin(
                host.id,
                f"game:{game.id}:advance",
                idempotency_key,
                request_fingerprint="{}",
                now=checked_at,
            )
            if idempotency is not None and idempotency.replay_payload is not None:
                return AdvanceCommandResult(idempotency.replay_payload, True)
            round_record = await self.rounds.lock_current_for_game(game.id)
            if round_record is None:
                raise ResourceNotFoundError("Current round not found")
            recovered_deadline = await self._close_if_due(
                game,
                round_record,
                now=checked_at,
            )
            if not recovered_deadline:
                if round_record.status is not RoundStatus.REVIEW:
                    raise InvalidStateError("Current round is not ready to advance")
                round_record.status = RoundStatus.COMPLETED
                round_record.is_current = False
                await self.session.flush()

                if round_record.sequence_number >= game.round_count:
                    game.status = GameStatus.COMPLETED
                    game.completed_at = checked_at
                    result = AdvanceResult(game.status, None)
                    await self.outbox.stage(
                        game.room_code,
                        "game.completed",
                        {"game_status": game.status.value, "current_round": None},
                        occurred_at=checked_at,
                    )
                else:
                    used_letters = await self.rounds.list_used_letters(game.id)
                    next_round = await self.rounds.add(
                        Round(
                            game_id=game.id,
                            sequence_number=round_record.sequence_number + 1,
                            letter=select_unused_letter(set(used_letters)),
                            status=RoundStatus.ACTIVE,
                            is_current=True,
                            starts_at=checked_at,
                            ends_at=checked_at
                            + timedelta(seconds=game.round_duration_seconds),
                        )
                    )
                    result = AdvanceResult(game.status, next_round)
                    await self.outbox.stage(
                        game.room_code,
                        "round.started",
                        {
                            "game_status": game.status.value,
                            "current_round": self._round_event_payload(next_round),
                        },
                        occurred_at=checked_at,
                    )
                if result is not None:
                    await self.idempotency.complete(
                        idempotency,
                        {
                            "game_status": result.game_status.value,
                            "current_round": (
                                self._round_event_payload(result.current_round)
                                if result.current_round is not None
                                else None
                            ),
                        },
                        completed_at=checked_at,
                    )
        if recovered_deadline:
            raise InvalidStateError("Round was closed; review it before advancing")
        if result is None:
            raise RuntimeError("Round was not advanced")
        return AdvanceCommandResult(result, False)

    async def get_leaderboard(
        self,
        room_code: str,
        session_token: str,
    ) -> GameLeaderboard:
        async with self.session.begin():
            game = await self.games.get_by_room_code(room_code)
            if game is None:
                raise ResourceNotFoundError("Game not found")
            await self._authorize(game, session_token)
            rows = await self.scores.get_leaderboard(game.id)
            entries: list[LeaderboardEntry] = []
            previous_total: int | None = None
            rank = 0
            for position, row in enumerate(rows, start=1):
                if row.total_score != previous_total:
                    rank = position
                    previous_total = row.total_score
                entries.append(
                    LeaderboardEntry(
                        rank=rank,
                        player_id=row.player_id,
                        display_name=row.display_name,
                        total_score=row.total_score,
                    )
                )
        return GameLeaderboard(game.id, tuple(entries))
