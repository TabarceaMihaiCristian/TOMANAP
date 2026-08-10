"""Transactional anonymous lobby and game-start lifecycle."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import MAX_PLAYERS, MIN_PLAYERS
from app.core.exceptions import (
    CapabilityDeniedError,
    DomainError,
    DuplicateDisplayNameError,
    InvalidStateError,
    LobbyFullError,
    ResourceNotFoundError,
)
from app.core.security import generate_room_code
from app.models import Game, Player, Round
from app.models.enums import GameStatus, RoundStatus
from app.repositories.games import GameRepository
from app.repositories.players import PlayerRepository
from app.repositories.rounds import RoundRepository
from app.services.event_outbox import EventOutbox
from app.services.idempotency import IdempotencyService
from app.services.letters import select_unused_letter, validate_round_count
from app.services.sessions import AnonymousSessionService, SessionTokens
from app.utilities.datetime import utc_now
from app.utilities.text import clean_answer, normalize_answer


@dataclass(frozen=True, slots=True)
class PlayerSnapshot:
    """Token-free public membership state."""

    id: UUID
    display_name: str
    seat_number: int
    is_host: bool
    is_ready: bool
    is_connected: bool


@dataclass(frozen=True, slots=True)
class GameSnapshot:
    """Token-free public game and lobby state."""

    id: UUID
    room_code: str
    status: GameStatus
    round_count: int
    round_duration_seconds: int
    players: tuple[PlayerSnapshot, ...]


@dataclass(frozen=True, slots=True)
class LobbySessionResult:
    """New or restored membership plus one-time plaintext credentials."""

    game: GameSnapshot
    player_id: UUID
    tokens: SessionTokens


@dataclass(frozen=True, slots=True)
class StartGameResult:
    """Live or replayed game-start response."""

    game: GameSnapshot | dict[str, object]
    replayed: bool


class LobbyService:
    """Apply room mutations under service-owned database transactions."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        room_code_factory: Callable[[], str] = generate_room_code,
    ) -> None:
        self.session = session
        self.settings = settings
        self.games = GameRepository(session)
        self.players = PlayerRepository(session)
        self.rounds = RoundRepository(session)
        self.anonymous_sessions = AnonymousSessionService(session, settings)
        self.outbox = EventOutbox(session)
        self.idempotency = IdempotencyService(session, settings)
        self.room_code_factory = room_code_factory

    @staticmethod
    def _display_name(value: str) -> tuple[str, str]:
        display_name = clean_answer(value)
        normalized_name = normalize_answer(display_name)
        if not display_name or not normalized_name:
            raise DomainError("Display name must contain letters or numbers")
        if len(display_name) > 40 or len(normalized_name) > 40:
            raise DomainError("Display name must not exceed 40 characters")
        return display_name, normalized_name

    @staticmethod
    def _require_lobby(game: Game) -> None:
        if game.status is not GameStatus.LOBBY:
            raise InvalidStateError("Game is no longer in the lobby")

    @staticmethod
    def _require_host(player: Player) -> None:
        if not player.is_host:
            raise CapabilityDeniedError("Only the host can perform this action")

    async def _game_by_code(self, room_code: str, *, locked: bool = False) -> Game:
        game = (
            await self.games.lock_by_room_code(room_code)
            if locked
            else await self.games.get_by_room_code(room_code)
        )
        if game is None:
            raise ResourceNotFoundError("Game not found")
        return game

    async def _authorize(self, game: Game, session_token: str) -> Player:
        context = await self.anonymous_sessions.authenticate(session_token)
        if context.game.id != game.id:
            raise CapabilityDeniedError("Session does not belong to this game")
        return context.player

    async def _snapshot(self, game: Game) -> GameSnapshot:
        players = await self.players.list_for_game(game.id)
        return GameSnapshot(
            id=game.id,
            room_code=game.room_code,
            status=game.status,
            round_count=game.round_count,
            round_duration_seconds=game.round_duration_seconds,
            players=tuple(
                PlayerSnapshot(
                    id=player.id,
                    display_name=player.display_name,
                    seat_number=player.seat_number,
                    is_host=player.is_host,
                    is_ready=player.is_ready,
                    is_connected=player.is_connected,
                )
                for player in players
            ),
        )

    async def get_public_state(self, room_code: str) -> GameSnapshot:
        game = await self._game_by_code(room_code)
        return await self._snapshot(game)

    async def get_state_by_id(self, game_id: UUID) -> GameSnapshot:
        game = await self.games.get_by_id(game_id)
        if game is None:
            raise ResourceNotFoundError("Game not found")
        return await self._snapshot(game)

    async def create_game(
        self,
        display_name: str,
        *,
        round_count: int,
        round_duration_seconds: int,
    ) -> LobbySessionResult:
        cleaned_name, normalized_name = self._display_name(display_name)
        validate_round_count(round_count)
        if not 1 <= round_duration_seconds <= 600:
            raise ValueError("round_duration_seconds must be between 1 and 600")

        async with self.session.begin():
            game: Game | None = None
            for _attempt in range(self.settings.room_code_generation_attempts):
                candidate = Game(
                    room_code=self.room_code_factory(),
                    round_count=round_count,
                    round_duration_seconds=round_duration_seconds,
                )
                try:
                    async with self.session.begin_nested():
                        game = await self.games.add(candidate)
                except IntegrityError:
                    game = None
                    continue
                break
            if game is None:
                raise RuntimeError("Could not allocate a unique room code")

            host = await self.players.add(
                Player(
                    game_id=game.id,
                    display_name=cleaned_name,
                    normalized_display_name=normalized_name,
                    seat_number=1,
                    is_host=True,
                )
            )
            _record, tokens = await self.anonymous_sessions.issue_for_player(host.id)
            snapshot = await self._snapshot(game)
            await self.outbox.stage(
                game.room_code,
                "lobby.created",
                {"game": snapshot},
            )
        return LobbySessionResult(snapshot, host.id, tokens)

    async def join_game(
        self,
        room_code: str,
        display_name: str,
    ) -> LobbySessionResult:
        cleaned_name, normalized_name = self._display_name(display_name)
        async with self.session.begin():
            game = await self._game_by_code(room_code, locked=True)
            self._require_lobby(game)
            players = await self.players.list_for_game(game.id)
            if len(players) >= MAX_PLAYERS:
                raise LobbyFullError("Lobby is full")
            if await self.players.normalized_name_exists(game.id, normalized_name):
                raise DuplicateDisplayNameError(
                    "An active player already uses this display name"
                )

            occupied_seats = {player.seat_number for player in players}
            seat_number = next(
                seat for seat in range(1, MAX_PLAYERS + 1) if seat not in occupied_seats
            )
            player = await self.players.add(
                Player(
                    game_id=game.id,
                    display_name=cleaned_name,
                    normalized_display_name=normalized_name,
                    seat_number=seat_number,
                )
            )
            _record, tokens = await self.anonymous_sessions.issue_for_player(player.id)
            snapshot = await self._snapshot(game)
            await self.outbox.stage(
                game.room_code,
                "lobby.updated",
                {"reason": "player_joined", "game": snapshot},
            )
        return LobbySessionResult(snapshot, player.id, tokens)

    async def set_ready(
        self,
        room_code: str,
        session_token: str,
        *,
        is_ready: bool,
    ) -> GameSnapshot:
        async with self.session.begin():
            game = await self._game_by_code(room_code, locked=True)
            self._require_lobby(game)
            player = await self._authorize(game, session_token)
            player.is_ready = is_ready
            snapshot = await self._snapshot(game)
            await self.outbox.stage(
                game.room_code,
                "lobby.updated",
                {"reason": "player_ready_changed", "game": snapshot},
            )
        return snapshot

    async def leave_game(
        self,
        room_code: str,
        session_token: str,
    ) -> GameSnapshot:
        async with self.session.begin():
            game = await self._game_by_code(room_code, locked=True)
            self._require_lobby(game)
            player = await self._authorize(game, session_token)
            was_host = player.is_host
            player.is_host = False
            player.is_ready = False
            player.is_active = False
            player.is_connected = False
            player.left_at = utc_now()
            await self.anonymous_sessions.revoke_player_sessions(player.id)
            await self.session.flush()

            if was_host:
                remaining = await self.players.list_for_game(game.id)
                if remaining:
                    remaining[0].is_host = True
            snapshot = await self._snapshot(game)
            await self.outbox.stage(
                game.room_code,
                "lobby.updated",
                {"reason": "player_left", "game": snapshot},
            )
        return snapshot

    async def update_settings(
        self,
        room_code: str,
        session_token: str,
        *,
        round_count: int | None,
        round_duration_seconds: int | None,
    ) -> GameSnapshot:
        async with self.session.begin():
            game = await self._game_by_code(room_code, locked=True)
            self._require_lobby(game)
            player = await self._authorize(game, session_token)
            self._require_host(player)
            if round_count is not None:
                game.round_count = validate_round_count(round_count)
            if round_duration_seconds is not None:
                if not 1 <= round_duration_seconds <= 600:
                    raise ValueError("round_duration_seconds must be between 1 and 600")
                game.round_duration_seconds = round_duration_seconds
            snapshot = await self._snapshot(game)
            await self.outbox.stage(
                game.room_code,
                "lobby.updated",
                {"reason": "settings_changed", "game": snapshot},
            )
        return snapshot

    async def start_game(
        self,
        room_code: str,
        session_token: str,
        *,
        started_at: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> StartGameResult:
        async with self.session.begin():
            game = await self._game_by_code(room_code, locked=True)
            host = await self._authorize(game, session_token)
            self._require_host(host)
            authoritative_start = started_at or utc_now()
            idempotency = await self.idempotency.begin(
                host.id,
                f"game:{game.id}:start",
                idempotency_key,
                request_fingerprint="{}",
                now=authoritative_start,
            )
            if idempotency is not None and idempotency.replay_payload is not None:
                return StartGameResult(idempotency.replay_payload, True)

            self._require_lobby(game)
            players = await self.players.list_for_game(game.id)
            if len(players) < MIN_PLAYERS:
                raise InvalidStateError(
                    f"At least {MIN_PLAYERS} active players are required"
                )
            if any(not player.is_host and not player.is_ready for player in players):
                raise InvalidStateError("Every non-host player must be ready")

            game.status = GameStatus.IN_PROGRESS
            game.started_at = authoritative_start
            await self.rounds.add(
                Round(
                    game_id=game.id,
                    sequence_number=1,
                    letter=select_unused_letter(set()),
                    status=RoundStatus.ACTIVE,
                    is_current=True,
                    starts_at=authoritative_start,
                    ends_at=authoritative_start
                    + timedelta(seconds=game.round_duration_seconds),
                )
            )
            snapshot = await self._snapshot(game)
            await self.outbox.stage(
                game.room_code,
                "game.started",
                {"game": snapshot},
                occurred_at=authoritative_start,
            )
            await self.idempotency.complete(
                idempotency,
                snapshot,
                completed_at=authoritative_start,
            )
        return StartGameResult(snapshot, False)
