"""Low-level HTTP resource limits applied before request parsing."""

from collections.abc import Awaitable, Callable

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import Message, Receive, Scope, Send

ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class RequestBodyTooLarge(Exception):
    """Signal that a streamed body crossed its configured limit."""


class RequestBodyLimitMiddleware:
    """Reject oversized declared and streamed HTTP request bodies."""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        if max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = 0
            if declared_length > self.max_body_bytes:
                await self._reject(scope, receive, send)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise RequestBodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "request_too_large",
                    "message": "Request body is too large",
                }
            },
        )
        await response(scope, receive, send)
