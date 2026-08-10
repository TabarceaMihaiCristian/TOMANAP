"""Draft replacement and idempotent finalization endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_database_session,
    get_outbox_dispatcher,
    get_request_settings,
    get_session_token,
)
from app.core.config import Settings
from app.schemas.submission import SubmissionResponse, SubmissionUpsertRequest
from app.services.outbox import OutboxDispatcher
from app.services.rounds import RoundService

router = APIRouter(prefix="/rounds", tags=["submissions"])


@router.put("/{round_id}/submission", response_model=SubmissionResponse)
async def upsert_submission(
    round_id: UUID,
    request: SubmissionUpsertRequest,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> SubmissionResponse:
    """Replace the caller's complete draft before it becomes immutable."""
    result = await RoundService(session, settings).upsert_submission(
        round_id,
        session_token,
        request.answers.model_dump(),
    )
    submission = result.submission
    response = SubmissionResponse.model_validate(submission)
    await dispatcher.dispatch_once()
    return response


@router.post(
    "/{round_id}/submission/finalize",
    response_model=SubmissionResponse,
)
async def finalize_submission(
    round_id: UUID,
    session_token: Annotated[str, Depends(get_session_token)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    dispatcher: Annotated[OutboxDispatcher, Depends(get_outbox_dispatcher)],
) -> SubmissionResponse:
    """Lock the caller's answers and close early when everyone is done."""
    result = await RoundService(session, settings).finalize_submission(
        round_id,
        session_token,
    )
    submission = result.submission
    response = SubmissionResponse.model_validate(submission)
    await dispatcher.dispatch_once()
    return response
