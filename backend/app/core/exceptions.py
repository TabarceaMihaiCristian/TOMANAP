"""Typed exceptions for expected domain failures."""

from http import HTTPStatus
from typing import Any


class DomainError(Exception):
    """Base class for failures safe to expose through the API."""

    code = "domain_error"
    status_code = HTTPStatus.BAD_REQUEST

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ResourceNotFoundError(DomainError):
    """Raised when a requested domain resource does not exist."""

    code = "not_found"
    status_code = HTTPStatus.NOT_FOUND


class CapabilityDeniedError(DomainError):
    """Raised when an anonymous session lacks a required capability."""

    code = "capability_denied"
    status_code = HTTPStatus.FORBIDDEN


class InvalidStateError(DomainError):
    """Raised when an action violates the current state machine."""

    code = "invalid_state"
    status_code = HTTPStatus.CONFLICT


class InvalidSessionError(DomainError):
    """Raised when an anonymous session token cannot authorize a request."""

    code = "invalid_session"
    status_code = HTTPStatus.UNAUTHORIZED

    def __init__(self, message: str = "Invalid or expired session") -> None:
        super().__init__(message)


class DuplicateDisplayNameError(DomainError):
    """Raised when an active room member already uses the normalized name."""

    code = "duplicate_display_name"
    status_code = HTTPStatus.CONFLICT


class LobbyFullError(DomainError):
    """Raised when no active player seat remains in a lobby."""

    code = "lobby_full"
    status_code = HTTPStatus.CONFLICT


class RateLimitExceededError(DomainError):
    """Raised when an entry endpoint exceeds its abuse budget."""

    code = "rate_limit_exceeded"
    status_code = HTTPStatus.TOO_MANY_REQUESTS

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many requests")
        self.retry_after_seconds = retry_after_seconds


class IdempotencyConflictError(DomainError):
    """Raised when a command key cannot safely be replayed."""

    code = "idempotency_conflict"
    status_code = HTTPStatus.CONFLICT
