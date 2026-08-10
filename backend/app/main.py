"""FastAPI application factory and process entrypoint."""

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import api_router
from app.core.config import Settings, get_settings
from app.core.http import RequestBodyLimitMiddleware
from app.core.logging import configure_logging, request_id_context
from app.core.rate_limiting import SlidingWindowRateLimiter
from app.db.session import Database
from app.services.maintenance import MaintenanceService, MaintenanceWorker
from app.services.outbox import OutboxDispatcher, OutboxWorker
from app.services.readiness import ReadinessService
from app.services.realtime import RealtimeBroker
from app.services.realtime_connections import RealtimeConnectionManager
from app.services.redis_adapters import RedisRateLimiter, RedisRealtimeBroker
from app.services.telemetry import Telemetry
from app.services.timers import DeadlineSweeper, DeadlineWorker

SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": (
        "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}
DOCS_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    "script-src https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src https://fastapi.tiangolo.com data:; "
    "connect-src 'self'; frame-ancestors 'none'"
)
audit_logger = logging.getLogger("app.audit")


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    if SAFE_REQUEST_ID.fullmatch(supplied):
        return supplied
    return uuid4().hex


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    realtime_broker: RealtimeBroker | RedisRealtimeBroker | None = None,
    telemetry: Telemetry | None = None,
) -> FastAPI:
    """Build an isolated TOMANAP application instance."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    resolved_database = database or Database(
        resolved_settings.database_url,
        echo=resolved_settings.database_echo,
    )
    resolved_telemetry = telemetry or Telemetry(resolved_settings)
    redis_client = (
        Redis.from_url(resolved_settings.redis_url, decode_responses=False)
        if resolved_settings.redis_url is not None
        else None
    )
    resolved_realtime_broker = realtime_broker or (
        RedisRealtimeBroker(
            redis_client,
            channel_prefix=resolved_settings.redis_channel_prefix,
        )
        if redis_client is not None
        else RealtimeBroker()
    )
    realtime_connections = RealtimeConnectionManager(
        max_connections_per_room=(resolved_settings.realtime_max_connections_per_room),
        max_connections_per_player=(
            resolved_settings.realtime_max_connections_per_player
        ),
    )
    entry_rate_limiter = (
        RedisRateLimiter(
            redis_client,
            requests=resolved_settings.entry_rate_limit_requests,
            window_seconds=resolved_settings.entry_rate_limit_window_seconds,
            key_prefix=resolved_settings.redis_rate_limit_prefix,
        )
        if redis_client is not None
        else SlidingWindowRateLimiter(
            requests=resolved_settings.entry_rate_limit_requests,
            window_seconds=resolved_settings.entry_rate_limit_window_seconds,
            max_keys=resolved_settings.entry_rate_limit_max_keys,
        )
    )
    outbox_dispatcher = OutboxDispatcher(
        resolved_database,
        resolved_realtime_broker,
        batch_size=resolved_settings.outbox_batch_size,
        lease_seconds=resolved_settings.outbox_lease_seconds,
        retry_base_seconds=resolved_settings.outbox_retry_base_seconds,
        retry_max_seconds=resolved_settings.outbox_retry_max_seconds,
    )
    outbox_worker = OutboxWorker(
        outbox_dispatcher,
        interval_seconds=resolved_settings.outbox_dispatch_interval_seconds,
    )
    deadline_sweeper = DeadlineSweeper(
        resolved_database,
        resolved_settings,
        outbox_dispatcher,
    )
    deadline_worker = DeadlineWorker(
        deadline_sweeper,
        interval_seconds=resolved_settings.deadline_sweep_interval_seconds,
    )
    maintenance_service = MaintenanceService(resolved_database, resolved_settings)
    maintenance_worker = MaintenanceWorker(
        maintenance_service,
        interval_seconds=resolved_settings.maintenance_interval_seconds,
    )
    readiness = ReadinessService(
        resolved_database,
        redis=redis_client,
        workers=(
            (bool(resolved_settings.deadline_worker_enabled), deadline_worker),
            (bool(resolved_settings.outbox_worker_enabled), outbox_worker),
            (bool(resolved_settings.maintenance_worker_enabled), maintenance_worker),
        ),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if resolved_settings.deadline_worker_enabled:
            await deadline_worker.start()
        if resolved_settings.outbox_worker_enabled:
            await outbox_worker.start()
        if resolved_settings.maintenance_worker_enabled:
            await maintenance_worker.start()
        try:
            yield
        finally:
            _app.state.draining = True
            await realtime_connections.begin_draining()
            await realtime_connections.wait_until_empty(
                timeout_seconds=resolved_settings.shutdown_grace_seconds
            )
            if outbox_worker.is_running:
                await outbox_worker.stop()
            if deadline_worker.is_running:
                await deadline_worker.stop()
            if maintenance_worker.is_running:
                await maintenance_worker.stop()
            if redis_client is not None:
                await redis_client.aclose()
            await resolved_database.dispose()
            await asyncio.to_thread(resolved_telemetry.shutdown)

    docs_url = "/docs" if resolved_settings.docs_enabled else None
    openapi_url = "/openapi.json" if resolved_settings.docs_enabled else None
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database = resolved_database
    app.state.realtime_broker = resolved_realtime_broker
    app.state.realtime_connections = realtime_connections
    app.state.deadline_sweeper = deadline_sweeper
    app.state.deadline_worker = deadline_worker
    app.state.entry_rate_limiter = entry_rate_limiter
    app.state.redis = redis_client
    app.state.outbox_dispatcher = outbox_dispatcher
    app.state.outbox_worker = outbox_worker
    app.state.maintenance_service = maintenance_service
    app.state.maintenance_worker = maintenance_worker
    app.state.readiness = readiness
    app.state.draining = False
    app.state.telemetry = resolved_telemetry

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(resolved_settings.allowed_hosts),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Idempotency-Key",
            "X-TOMANAP-Session",
            "X-Request-ID",
        ],
        expose_headers=["Idempotency-Replayed", "X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_bytes=resolved_settings.max_request_body_bytes,
    )

    @app.middleware("http")
    async def add_request_context(
        request: Request,
        call_next,
    ) -> Response:
        request_id = _request_id(request)
        started_at = time.perf_counter()
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            for name, value in SECURITY_HEADERS.items():
                response.headers[name] = value
            if resolved_settings.docs_enabled and request.url.path == "/docs":
                response.headers["Content-Security-Policy"] = (
                    DOCS_CONTENT_SECURITY_POLICY
                )
            route = request.scope.get("route")
            audit_logger.info(
                "request.completed",
                extra={
                    "event": "request.completed",
                    "method": request.method,
                    "route": getattr(route, "path", "unmatched"),
                    "status_code": response.status_code,
                    "duration_ms": round(
                        (time.perf_counter() - started_at) * 1000,
                        3,
                    ),
                },
            )
            return response
        finally:
            request_id_context.reset(token)

    register_exception_handlers(app)
    app.include_router(api_router)
    resolved_telemetry.instrument(app, resolved_database.engine)
    return app


app = create_app()
