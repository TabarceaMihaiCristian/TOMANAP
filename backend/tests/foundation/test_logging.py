"""Tests for structured, correlation-aware logging."""

import json
import logging

from app.core.logging import JsonFormatter, request_id_context


def test_json_formatter_emits_stable_structured_fields() -> None:
    token = request_id_context.set("request-42")
    try:
        record = logging.LogRecord(
            name="tomanap.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="round started",
            args=(),
            exc_info=None,
        )
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(token)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "tomanap.test"
    assert payload["message"] == "round started"
    assert payload["request_id"] == "request-42"
    assert payload["timestamp"].endswith("Z")


def test_json_formatter_whitelists_safe_audit_fields() -> None:
    record = logging.LogRecord(
        name="app.audit",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request.completed",
        args=(),
        exc_info=None,
    )
    record.event = "request.completed"
    record.method = "POST"
    record.route = "/games/{room_code}/join"
    record.status_code = 201
    record.duration_ms = 12.5
    record.unlisted_sensitive_value = "must-not-be-serialized"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "request.completed"
    assert payload["method"] == "POST"
    assert payload["route"] == "/games/{room_code}/join"
    assert payload["status_code"] == 201
    assert payload["duration_ms"] == 12.5
    assert "unlisted_sensitive_value" not in payload
