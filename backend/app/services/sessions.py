"""Secure anonymous session issuance, authentication, and rotation."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import InvalidSessionError
from app.core.security import (
    generate_opaque_token,
    hash_token,
    verify_token,
)
from app.models import AnonymousSession, Game, Player
from app.repositories.games import GameRepository
from app.repositories.players import PlayerRepository
from app.repositories.sessions import SessionRepository
from app.services.event_outbox import EventOutbox
from app.utilities.datetime import as_utc, utc_now


@dataclass(frozen=True, slots=True)
class SessionTokens:
    """Plaintext credentials returned exactly once to a client."""

    session_token: str
    reconnect_token: str


@dataclass(frozen=True, slots=True)
class SessionContext:
    """Authenticated database entities for one anonymous capability."""

    anonymous_session: AnonymousSession
    player: Player
    game: Game


@dataclass(frozen=True, slots=True)
class RestoredSession:
    """Rotated credentials and their restored membership context."""

    context: SessionContext
    tokens: SessionTokens


class AnonymousSessionService:
    """Manage high-entropy capabilities without authentication accounts."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self.session = session
        self.settings = settings
        self.sessions = SessionRepository(session)
        self.players = PlayerRepository(session)
        self.games = GameRepository(session)
        self.outbox = EventOutbox(session)

    def _new_tokens(self) -> SessionTokens:
        return SessionTokens(
            session_token=generate_opaque_token(),
            reconnect_token=generate_opaque_token(),
        )

    async def issue_for_player(
        self,
        player_id,
        *,
        now: datetime | None = None,
    ) -> tuple[AnonymousSession, SessionTokens]:
        """Stage a new hashed session inside the caller's transaction."""
        issued_at = now or utc_now()
        tokens = self._new_tokens()
        anonymous_session = AnonymousSession(
            player_id=player_id,
            session_token_hash=hash_token(tokens.session_token),
            reconnect_token_hash=hash_token(tokens.reconnect_token),
            expires_at=issued_at + timedelta(minutes=self.settings.session_ttl_minutes),
            reconnect_expires_at=issued_at
            + timedelta(days=self.settings.reconnect_ttl_days),
            last_seen_at=issued_at,
        )
        await self.sessions.add(anonymous_session)
        return anonymous_session, tokens

    async def authenticate(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> SessionContext:
        """Resolve an active session inside the caller's transaction."""
        checked_at = now or utc_now()
        token_hash = hash_token(token)
        anonymous_session = await self.sessions.get_by_session_token_hash(token_hash)
        if (
            anonymous_session is None
            or not verify_token(token, anonymous_session.session_token_hash)
            or anonymous_session.revoked_at is not None
            or as_utc(anonymous_session.expires_at) <= checked_at
        ):
            raise InvalidSessionError()

        player = await self.players.get_by_id(anonymous_session.player_id)
        if player is None or not player.is_active:
            raise InvalidSessionError()
        game = await self.games.get_by_id(player.game_id)
        if game is None:
            raise InvalidSessionError()

        anonymous_session.last_seen_at = checked_at
        return SessionContext(anonymous_session, player, game)

    async def restore(
        self,
        reconnect_token: str,
        *,
        now: datetime | None = None,
    ) -> RestoredSession:
        """Atomically rotate both credentials for an active player seat."""
        checked_at = now or utc_now()
        reconnect_hash = hash_token(reconnect_token)
        async with self.session.begin():
            anonymous_session = await self.sessions.lock_by_reconnect_token_hash(
                reconnect_hash
            )
            if (
                anonymous_session is None
                or not verify_token(
                    reconnect_token,
                    anonymous_session.reconnect_token_hash,
                )
                or anonymous_session.revoked_at is not None
                or as_utc(anonymous_session.reconnect_expires_at) <= checked_at
            ):
                raise InvalidSessionError()

            player = await self.players.get_by_id(anonymous_session.player_id)
            if player is None or not player.is_active:
                raise InvalidSessionError()
            player.is_connected = True
            player.last_seen_at = checked_at
            game = await self.games.get_by_id(player.game_id)
            if game is None:
                raise InvalidSessionError()

            tokens = self._new_tokens()
            anonymous_session.session_token_hash = hash_token(tokens.session_token)
            anonymous_session.reconnect_token_hash = hash_token(tokens.reconnect_token)
            anonymous_session.expires_at = checked_at + timedelta(
                minutes=self.settings.session_ttl_minutes
            )
            anonymous_session.reconnect_expires_at = checked_at + timedelta(
                days=self.settings.reconnect_ttl_days
            )
            anonymous_session.last_seen_at = checked_at
            await self.session.flush()
            await self.outbox.stage(
                game.room_code,
                "lobby.updated",
                {
                    "reason": "player_reconnected",
                    "player_id": str(player.id),
                },
                occurred_at=checked_at,
            )
            context = SessionContext(anonymous_session, player, game)
        return RestoredSession(context, tokens)

    async def revoke_player_sessions(
        self,
        player_id,
        *,
        now: datetime | None = None,
    ) -> None:
        """Stage revocation of every credential associated with a seat."""
        revoked_at = now or utc_now()
        for anonymous_session in await self.sessions.list_for_player(player_id):
            anonymous_session.revoked_at = revoked_at
