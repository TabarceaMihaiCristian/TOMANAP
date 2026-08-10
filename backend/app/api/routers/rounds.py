"""Current-round, review, and host advancement endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_database_session,
    get_outbox_dispatcher,
    get_request_settings,
    get_session_token,
)
from app.core.config import Settings
from app.core.constants import CATEGORIES
from app.schemas.round import (
    CurrentRoundResponse,
    RoundAdvanceResponse,
    RoundResponse,
    RoundReviewResponse,
)
from app.schemas.submission import SubmissionResponse
from app.services.outbox import OutboxDispatcher
from app.services.rounds import RoundService

router = APIRouter(tags=["rounds"])


@router.get(
    "/games/{room_code}/rounds/current",
    response_model=CurrentRoundResponse,
)
async def get_current_round(
    room_code: str,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> CurrentRoundResponse:
    """Return current authoritative state and only the caller's draft."""
    result = await RoundService(session, settings).get_current(
        room_code,
        session_token,
    )
    response = CurrentRoundResponse(
        round=RoundResponse.model_validate(result.round),
        categories=CATEGORIES,
        submission=(
            SubmissionResponse.model_validate(result.submission)
            if result.submission is not None
            else None
        ),
    )
    await dispatcher.dispatch_once()
    return response


@router.get("/rounds/{round_id}/review", response_model=RoundReviewResponse)
async def get_round_review(
    round_id: UUID,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> RoundReviewResponse:
    """Return auditable results after early or deadline closure."""
    review = await RoundService(session, settings).get_review(
        round_id,
        session_token,
    )
    response = RoundReviewResponse.model_validate(review, from_attributes=True)
    await dispatcher.dispatch_once()
    return response


@router.post(
    "/games/{room_code}/rounds/next",
    response_model=RoundAdvanceResponse,
)
async def advance_round(
    room_code: str,
    response_headers: Response,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
        ),
    ] = None,
) -> RoundAdvanceResponse:
    """Let the host leave review and create the next round or finish."""
    command = await RoundService(session, settings).advance(
        room_code,
        session_token,
        idempotency_key=idempotency_key,
    )
    response = RoundAdvanceResponse.model_validate(
        command.value,
        from_attributes=True,
    )
    if command.replayed:
        response_headers.headers["Idempotency-Replayed"] = "true"
    await dispatcher.dispatch_once()
    return response
