"""Typed application settings loaded from environment variables."""

from enum import StrEnum
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Validated TOMANAP configuration.

    Environment variables use the ``TOMANAP_`` prefix. Lists are represented
    as JSON arrays, which avoids ambiguous comma parsing for URLs.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TOMANAP_",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="TOMANAP API", min_length=1, max_length=80)
    app_version: str = Field(default="0.1.0", min_length=1, max_length=32)
    environment: Environment = Environment.DEVELOPMENT
    database_url: str = "sqlite+aiosqlite:///./tomanap.db"
    database_echo: bool = False
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    allowed_hosts: tuple[str, ...] = (
        "localhost",
        "127.0.0.1",
        "testserver",
    )
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    docs_enabled: bool | None = None
    session_ttl_minutes: int = Field(default=120, ge=5, le=1440)
    reconnect_ttl_days: int = Field(default=7, ge=1, le=30)
    room_code_generation_attempts: int = Field(default=8, ge=1, le=32)
    deadline_worker_enabled: bool | None = None
    deadline_sweep_interval_seconds: float = Field(default=1.0, ge=0.1, le=60)
    deadline_sweep_batch_size: int = Field(default=100, ge=1, le=1000)
    entry_rate_limit_requests: int = Field(default=60, ge=1, le=10000)
    entry_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    entry_rate_limit_max_keys: int = Field(default=10000, ge=100, le=1000000)
    outbox_worker_enabled: bool | None = None
    outbox_dispatch_interval_seconds: float = Field(default=0.25, ge=0.05, le=60)
    outbox_batch_size: int = Field(default=100, ge=1, le=1000)
    outbox_lease_seconds: float = Field(default=30, ge=1, le=300)
    outbox_retry_base_seconds: float = Field(default=1, ge=0.1, le=60)
    outbox_retry_max_seconds: float = Field(default=60, ge=1, le=3600)
    realtime_ticket_ttl_seconds: int = Field(default=30, ge=5, le=300)
    realtime_max_connections_per_room: int = Field(default=24, ge=1, le=1000)
    realtime_max_connections_per_player: int = Field(default=3, ge=1, le=20)
    realtime_heartbeat_seconds: float = Field(default=20, ge=1, le=120)
    realtime_idle_timeout_seconds: float = Field(default=60, ge=5, le=600)
    realtime_max_message_bytes: int = Field(default=4096, ge=256, le=65536)
    idempotency_ttl_hours: int = Field(default=24, ge=1, le=168)
    max_request_body_bytes: int = Field(default=65536, ge=1024, le=1048576)
    shutdown_grace_seconds: float = Field(default=10, ge=0, le=120)
    maintenance_worker_enabled: bool | None = None
    maintenance_interval_seconds: float = Field(default=3600, ge=60, le=86400)
    maintenance_batch_size: int = Field(default=100, ge=1, le=1000)
    credential_retention_hours: int = Field(default=24, ge=1, le=168)
    outbox_retention_days: int = Field(default=7, ge=1, le=90)
    completed_game_retention_days: int = Field(default=30, ge=1, le=365)
    telemetry_enabled: bool = False
    telemetry_otlp_endpoint: str | None = None
    telemetry_export_interval_seconds: int = Field(default=30, ge=1, le=300)
    redis_url: str | None = None
    redis_channel_prefix: str = Field(
        default="tomanap:room",
        min_length=1,
        max_length=80,
    )
    redis_rate_limit_prefix: str = Field(
        default="tomanap:rate",
        min_length=1,
        max_length=80,
    )

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("redis://", "rediss://")):
            raise ValueError("redis_url must use redis or rediss")
        return value

    @field_validator("telemetry_otlp_endpoint")
    @classmethod
    def validate_telemetry_endpoint(cls, value: str | None) -> str | None:
        """Accept an HTTP(S) OTLP base URL without embedded credentials."""
        if value is None:
            return None
        endpoint = value.strip().rstrip("/")
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Invalid telemetry_otlp_endpoint")
        return endpoint

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Limit connections to the async drivers supported by the app."""
        supported_prefixes = (
            "sqlite+aiosqlite://",
            "postgresql+asyncpg://",
        )
        if not value.startswith(supported_prefixes):
            message = "database_url must use sqlite+aiosqlite or postgresql+asyncpg"
            raise ValueError(message)
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Reject wildcard and malformed browser origins."""
        normalized: list[str] = []
        for raw_origin in values:
            origin = raw_origin.strip().rstrip("/")
            parsed = urlsplit(origin)
            try:
                _ = parsed.port
            except ValueError as error:
                raise ValueError(f"Invalid CORS origin: {raw_origin!r}") from error
            if (
                raw_origin == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"Invalid CORS origin: {raw_origin!r}")
            normalized.append(origin)
        if len(set(normalized)) != len(normalized):
            raise ValueError("cors_origins must not contain duplicates")
        return tuple(normalized)

    @field_validator("allowed_hosts")
    @classmethod
    def validate_allowed_hosts(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require explicit hostnames to prevent Host-header attacks."""
        normalized: list[str] = []
        for raw_host in values:
            host = raw_host.strip().lower()
            if not host or host == "*" or "/" in host or "\\" in host:
                raise ValueError(f"Invalid allowed host: {raw_host!r}")
            normalized.append(host)
        if len(set(normalized)) != len(normalized):
            raise ValueError("allowed_hosts must not contain duplicates")
        return tuple(normalized)

    @model_validator(mode="after")
    def choose_docs_default(self) -> Self:
        """Choose environment-sensitive service defaults."""
        if self.docs_enabled is None:
            self.docs_enabled = self.environment is not Environment.PRODUCTION
        if self.deadline_worker_enabled is None:
            self.deadline_worker_enabled = self.environment is not Environment.TEST
        if self.outbox_worker_enabled is None:
            self.outbox_worker_enabled = self.environment is not Environment.TEST
        if self.maintenance_worker_enabled is None:
            self.maintenance_worker_enabled = self.environment is not Environment.TEST
        if self.outbox_retry_max_seconds < self.outbox_retry_base_seconds:
            raise ValueError(
                "outbox_retry_max_seconds must not be smaller than its base"
            )
        if self.realtime_idle_timeout_seconds <= self.realtime_heartbeat_seconds:
            raise ValueError(
                "realtime_idle_timeout_seconds must exceed the heartbeat interval"
            )
        if self.telemetry_enabled and self.telemetry_otlp_endpoint is None:
            raise ValueError(
                "telemetry_otlp_endpoint is required when telemetry is enabled"
            )
        if self.environment is Environment.PRODUCTION:
            self._validate_production_invariants()
        return self

    def _validate_production_invariants(self) -> None:
        """Reject unsafe single-node or diagnostic production settings."""
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("Production requires PostgreSQL")
        if self.redis_url is None:
            raise ValueError("Production requires Redis")
        if not self.redis_url.startswith("rediss://"):
            raise ValueError("Production requires TLS Redis via rediss")
        if any(not origin.startswith("https://") for origin in self.cors_origins):
            raise ValueError("Production CORS origins must use HTTPS")
        local_hosts = {"localhost", "127.0.0.1", "::1", "testserver"}
        if any(host in local_hosts for host in self.allowed_hosts):
            raise ValueError("Production requires non-local allowed hosts")
        if self.docs_enabled:
            raise ValueError("Production docs must be disabled")
        if self.database_echo:
            raise ValueError("Production SQL echo must be disabled")
        if self.log_level == "DEBUG":
            raise ValueError("Production DEBUG logging is not allowed")
        if not self.deadline_worker_enabled:
            raise ValueError("Production deadline worker must be enabled")
        if not self.outbox_worker_enabled:
            raise ValueError("Production outbox worker must be enabled")
        if not self.maintenance_worker_enabled:
            raise ValueError("Production maintenance worker must be enabled")
        if not self.telemetry_enabled:
            raise ValueError("Production telemetry must be enabled")
        if not self.telemetry_otlp_endpoint.startswith("https://"):
            raise ValueError("Production requires an HTTPS telemetry endpoint")


def get_settings() -> Settings:
    """Load and validate settings for an application process."""
    return Settings()
