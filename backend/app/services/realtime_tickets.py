"""Issue and atomically consume short-lived WebSocket tickets."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import CapabilityDeniedError, InvalidSessionError
from app.core.security import generate_opaque_token, hash_token, verify_token
from app.models import Game, Player, RealtimeTicket
from app.repositories.games import GameRepository
from app.repositories.players import PlayerRepository
from app.repositories.realtime_tickets import RealtimeTicketRepository
from app.services.sessions import AnonymousSessionService
from app.utilities.datetime import as_utc, utc_now


@dataclass(frozen=True, slots=True)
class IssuedRealtimeTicket:
    """Plaintext ticket returned exactly once with its deadline."""

    ticket: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ConsumedRealtimeTicket:
    """Authenticated room membership recovered from a consumed ticket."""

    game: Game
    player: Player


class RealtimeTicketService:
    """Keep long-lived session capabilities out of WebSocket handshakes."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.games = GameRepository(session)
        self.players = PlayerRepository(session)
        self.tickets = RealtimeTicketRepository(session)
        self.sessions = AnonymousSessionService(session, settings)

    async def issue(
        self,
        room_code: str,
        session_token: str,
        *,
        now: datetime | None = None,
    ) -> IssuedRealtimeTicket:
        issued_at = now or utc_now()
        async with self.session.begin():
            game = await self.games.lock_by_room_code(room_code)
            if game is None:
                raise InvalidSessionError()
            context = await self.sessions.authenticate(session_token, now=issued_at)
            if context.game.id != game.id:
                raise CapabilityDeniedError("Session does not belong to this game")

            plaintext = generate_opaque_token()
            expires_at = issued_at + timedelta(
                seconds=self.settings.realtime_ticket_ttl_seconds
            )
            await self.tickets.add(
                RealtimeTicket(
                    game_id=game.id,
                    player_id=context.player.id,
                    ticket_hash=hash_token(plaintext),
                    expires_at=expires_at,
                )
            )
        return IssuedRealtimeTicket(plaintext, expires_at)

    async def consume(
        self,
        room_code: str,
        plaintext_ticket: str,
        *,
        now: datetime | None = None,
    ) -> ConsumedRealtimeTicket:
        checked_at = now or utc_now()
        ticket_hash = hash_token(plaintext_ticket)
        async with self.session.begin():
            ticket = await self.tickets.lock_by_hash(ticket_hash)
            if (
                ticket is None
                or not verify_token(plaintext_ticket, ticket.ticket_hash)
                or ticket.consumed_at is not None
                or as_utc(ticket.expires_at) <= checked_at
            ):
                raise InvalidSessionError("Invalid or expired realtime ticket")

            game = await self.games.get_by_id(ticket.game_id)
            player = await self.players.get_by_id(ticket.player_id)
            if (
                game is None
                or player is None
                or not player.is_active
                or game.room_code != room_code.strip().upper()
            ):
                raise InvalidSessionError("Invalid or expired realtime ticket")

            consumed = await self.tickets.consume_if_available(
                ticket.id,
                consumed_at=checked_at,
            )
            if not consumed:
                raise InvalidSessionError("Invalid or expired realtime ticket")
        return ConsumedRealtimeTicket(game, player)
