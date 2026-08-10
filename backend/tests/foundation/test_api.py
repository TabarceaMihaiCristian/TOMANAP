"""Integration tests for the FastAPI application foundation."""

import sqlite3
from contextlib import closing

from fastapi.testclient import TestClient

from app.core.config import Settings


def test_health_endpoint_reports_service_identity(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "TOMANAP API",
        "version": "0.1.0",
    }


def test_readiness_rejects_an_unmigrated_database(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": True,
            "migrations": False,
            "redis": True,
            "workers": True,
            "accepting_traffic": True,
        },
    }


def test_readiness_accepts_a_healthy_migrated_process(
    client: TestClient,
    settings: Settings,
) -> None:
    database_path = settings.database_url.removeprefix("sqlite+aiosqlite:///")
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32))")
            connection.execute(
                "INSERT INTO alembic_version VALUES (?)",
                ("d19f3b72a451",),
            )

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert all(response.json()["checks"].values())


def test_api_responses_include_defensive_headers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers["permissions-policy"] == (
        "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    )


def test_development_docs_use_a_narrow_docs_only_csp(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    policy = response.headers["content-security-policy"]
    assert "script-src https://cdn.jsdelivr.net" in policy
    assert "connect-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy


def test_request_id_is_echoed_only_when_safe(client: TestClient) -> None:
    accepted = client.get("/health", headers={"X-Request-ID": "mobile-123"})
    replaced = client.get("/health", headers={"X-Request-ID": "bad value\r\n"})

    assert accepted.headers["x-request-id"] == "mobile-123"
    assert replaced.headers["x-request-id"] != "bad value\r\n"
    assert len(replaced.headers["x-request-id"]) == 32


def test_cors_allows_only_configured_frontend(client: TestClient) -> None:
    allowed = client.options(
        "/health",
        headers={
            "Origin": "https://game.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    untrusted = client.options(
        "/health",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == (
        "https://game.example.test"
    )
    assert "access-control-allow-origin" not in untrusted.headers


def test_http_errors_use_a_stable_non_leaking_envelope(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}


def test_oversized_http_body_is_rejected_before_validation(
    client: TestClient,
) -> None:
    response = client.post(
        "/games",
        content=b"x" * 65537,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": {
            "code": "request_too_large",
            "message": "Request body is too large",
        }
    }
    assert response.headers["x-content-type-options"] == "nosniff"


def test_request_models_reject_mass_assignment_and_type_coercion(
    client: TestClient,
) -> None:
    extra_field = client.post(
        "/games",
        json={
            "display_name": "Mihai",
            "round_count": 3,
            "round_duration_seconds": 60,
            "status": "completed",
        },
    )
    coerced_type = client.post(
        "/games/ABC123/ready",
        headers={"X-TOMANAP-Session": "x" * 43},
        json={"is_ready": "false"},
    )

    assert extra_field.status_code == 422
    assert extra_field.json()["error"]["details"][0]["location"] == [
        "body",
        "status",
    ]
    assert coerced_type.status_code == 422
    assert coerced_type.json()["error"]["details"][0]["location"] == [
        "body",
        "is_ready",
    ]
