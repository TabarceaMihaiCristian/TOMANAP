"""Consistent, non-leaking HTTP exception responses."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import DomainError

logger = logging.getLogger(__name__)


def _error_payload(
    code: str,
    message: str,
    *,
    details: Any | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    """Register handlers for framework, validation, and domain failures."""

    @app.exception_handler(DomainError)
    async def handle_domain_error(
        _request: Request,
        exception: DomainError,
    ) -> JSONResponse:
        headers = None
        retry_after = getattr(exception, "retry_after_seconds", None)
        if retry_after is not None:
            headers = {"Retry-After": str(retry_after)}
        return JSONResponse(
            status_code=exception.status_code,
            content=_error_payload(
                exception.code,
                exception.message,
                details=exception.details,
            ),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {
                "location": list(error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exception.errors()
        ]
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=_error_payload(
                "validation_error",
                "Request validation failed",
                details=details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _request: Request,
        exception: StarletteHTTPException,
    ) -> JSONResponse:
        try:
            message = HTTPStatus(exception.status_code).phrase
        except ValueError:
            message = "HTTP error"
        code = "not_found" if exception.status_code == 404 else "http_error"
        return JSONResponse(
            status_code=exception.status_code,
            content=_error_payload(code, message),
            headers=exception.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        _request: Request,
        exception: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled application error", exc_info=exception)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=_error_payload(
                "internal_server_error",
                "An unexpected error occurred",
            ),
        )
