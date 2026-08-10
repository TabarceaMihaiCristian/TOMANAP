"""Liveness endpoint for TOMANAP deployments."""

from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Stable public service-health representation."""

    status: Literal["ok"]
    service: str
    version: str


class ReadinessResponse(BaseModel):
    """Public dependency readiness without infrastructure details."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Report process liveness without exposing infrastructure details."""
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    """Report whether the process can safely receive new traffic."""
    report = await request.app.state.readiness.check(
        accepting_traffic=not request.app.state.draining
    )
    if not report.is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if report.is_ready else "not_ready",
        checks=report.checks,
    )
