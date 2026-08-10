"""Timezone-aware UTC and deadline helpers."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current aware UTC time."""
    return datetime.now(UTC)


def require_aware(value: datetime, *, name: str) -> datetime:
    """Reject naive timestamps before they reach deadline comparisons."""
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def as_utc(value: datetime) -> datetime:
    """Convert aware timestamps, or SQLite's naive UTC values, to aware UTC."""
    if not isinstance(value, datetime):
        raise TypeError("value must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def deadline_reached(*, at: datetime, ends_at: datetime) -> bool:
    """Return whether ``at`` is at or after the exclusive deadline."""
    checked_at = require_aware(at, name="at")
    checked_end = require_aware(ends_at, name="ends_at")
    return checked_at >= checked_end
