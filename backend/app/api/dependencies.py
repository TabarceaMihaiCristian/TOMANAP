"""Shared FastAPI dependency providers."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import InvalidSessionError, RateLimitExceededError
from app.services.outbox import OutboxDispatcher
from app.services.realtime import RealtimeBroker


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one rollback-safe database session per request."""
    async with request.app.state.database.session() as session:
        yield session


def get_request_settings(request: Request) -> Settings:
    """Return the immutable application configuration for a request."""
    return request.app.state.settings


def get_realtime_broker(request: Request) -> RealtimeBroker:
    """Return the process-local room event broker."""
    return request.app.state.realtime_broker


def get_outbox_dispatcher(request: Request) -> OutboxDispatcher:
    """Return the durable event dispatcher used for immediate delivery."""
    return request.app.state.outbox_dispatcher


def get_session_token(request: Request) -> str:
    """Extract the anonymous capability header without logging its value."""
    token = request.headers.get("X-TOMANAP-Session")
    if token is None or not token.strip() or len(token) > 256:
        raise InvalidSessionError()
    return token


async def enforce_entry_rate_limit(request: Request) -> None:
    """Limit unauthenticated room/session entry points by client and route."""
    client_host = request.client.host if request.client is not None else "unknown"
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    decision = await request.app.state.entry_rate_limiter.check(
        f"{client_host}:{request.method}:{route_path}"
    )
    if not decision.allowed:
        raise RateLimitExceededError(decision.retry_after_seconds)
