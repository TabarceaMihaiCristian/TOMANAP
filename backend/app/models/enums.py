"""Persistence state enums for games and rounds."""

from enum import StrEnum


class GameStatus(StrEnum):
    """Authoritative game lifecycle states."""

    LOBBY = "lobby"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class RoundStatus(StrEnum):
    """Authoritative round lifecycle states."""

    PENDING = "pending"
    COUNTDOWN = "countdown"
    ACTIVE = "active"
    REVIEW = "review"
    COMPLETED = "completed"
