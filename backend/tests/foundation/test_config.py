"""Tests for typed environment-backed application settings."""

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings


def test_development_defaults_are_safe_and_usable() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "TOMANAP API"
    assert settings.app_version == "0.1.0"
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.database_url == "sqlite+aiosqlite:///./tomanap.db"
    assert settings.docs_enabled is True
    assert "*" not in settings.cors_origins
    assert "*" not in settings.allowed_hosts
    assert settings.shutdown_grace_seconds == 10
    assert settings.max_request_body_bytes == 65536
    assert settings.realtime_max_message_bytes == 4096


def test_settings_load_prefixed_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOMANAP_APP_NAME", "Configured TOMANAP")
    monkeypatch.setenv("TOMANAP_LOG_LEVEL", "WARNING")
    monkeypatch.setenv(
        "TOMANAP_CORS_ORIGINS",
        '["https://one.example", "https://two.example"]',
    )

    settings = Settings(_env_file=None)

    assert settings.app_name == "Configured TOMANAP"
    assert settings.log_level == "WARNING"
    assert settings.cors_origins == (
        "https://one.example",
        "https://two.example",
    )


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.PRODUCTION,
        "database_url": "postgresql+asyncpg://app:secret@db/tomanap",
        "redis_url": "rediss://redis:6379/0",
        "cors_origins": ("https://game.example.com",),
        "allowed_hosts": ("api.example.com",),
        "telemetry_enabled": True,
        "telemetry_otlp_endpoint": "https://otel.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_disables_docs_by_default() -> None:
    settings = _production_settings()

    assert settings.docs_enabled is False


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        (
            {"database_url": "sqlite+aiosqlite:///./prod.db"},
            "PostgreSQL",
        ),
        ({"redis_url": None}, "Redis"),
        ({"redis_url": "redis://redis:6379/0"}, "TLS Redis"),
        ({"cors_origins": ("http://game.example.com",)}, "HTTPS"),
        ({"allowed_hosts": ("localhost",)}, "non-local"),
        ({"docs_enabled": True}, "docs"),
        ({"database_echo": True}, "SQL echo"),
        ({"log_level": "DEBUG"}, "DEBUG"),
        ({"deadline_worker_enabled": False}, "deadline worker"),
        ({"outbox_worker_enabled": False}, "outbox worker"),
        ({"maintenance_worker_enabled": False}, "maintenance worker"),
        ({"telemetry_enabled": False}, "telemetry"),
        ({"telemetry_otlp_endpoint": "http://otel:4318"}, "HTTPS telemetry"),
    ],
)
def test_production_configuration_fails_closed(
    overrides: dict[str, object],
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        _production_settings(**overrides)


@pytest.mark.parametrize("field", ["cors_origins", "allowed_hosts"])
def test_wildcard_network_configuration_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: ("*",)})


@pytest.mark.parametrize(
    "origin",
    [
        "ftp://game.example",
        "https://game.example/a-path",
        "https://user:secret@game.example",
    ],
)
def test_malformed_or_credential_bearing_cors_origins_are_rejected(
    origin: str,
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=(origin,))


def test_enabled_telemetry_requires_a_well_formed_otlp_endpoint() -> None:
    with pytest.raises(ValidationError, match="telemetry_otlp_endpoint"):
        Settings(_env_file=None, telemetry_enabled=True)

    settings = Settings(
        _env_file=None,
        telemetry_enabled=True,
        telemetry_otlp_endpoint="http://localhost:4318/",
    )

    assert settings.telemetry_otlp_endpoint == "http://localhost:4318"
