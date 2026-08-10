"""Low-level tests that prevent declared-length limit bypasses."""

import json

from app.core.http import RequestBodyLimitMiddleware


async def test_streamed_body_limit_cannot_be_bypassed_by_false_content_length() -> None:
    messages = iter(
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"56789", "more_body": False},
        ]
    )
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return next(messages)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    async def consume_body(_scope, wrapped_receive, _send) -> None:  # type: ignore[no-untyped-def]
        while True:
            message = await wrapped_receive()
            if not message.get("more_body", False):
                return

    middleware = RequestBodyLimitMiddleware(consume_body, max_body_bytes=8)
    await middleware(
        {
            "type": "http",
            "method": "POST",
            "path": "/games",
            "headers": [(b"content-length", b"1")],
        },
        receive,  # type: ignore[arg-type]
        send,  # type: ignore[arg-type]
    )

    assert sent[0]["status"] == 413
    body = json.loads(sent[1]["body"])
    assert body["error"]["code"] == "request_too_large"
