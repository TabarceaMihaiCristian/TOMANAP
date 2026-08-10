"""Registered SQLAlchemy models for the TOMANAP domain."""

from app.models.game import Game
from app.models.idempotency import IdempotencyRecord
from app.models.outbox import OutboxEvent
from app.models.player import Player
from app.models.realtime_ticket import RealtimeTicket
from app.models.round import Round
from app.models.score import Score
from app.models.session import AnonymousSession
from app.models.submission import Submission

MODEL_REGISTRY = (
    Game,
    Player,
    AnonymousSession,
    Round,
    Submission,
    Score,
    OutboxEvent,
    RealtimeTicket,
    IdempotencyRecord,
)

__all__ = [
    "MODEL_REGISTRY",
    "AnonymousSession",
    "Game",
    "IdempotencyRecord",
    "OutboxEvent",
    "Player",
    "RealtimeTicket",
    "Round",
    "Score",
    "Submission",
]
