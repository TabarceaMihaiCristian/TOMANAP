"""Realtime ticket response schemas."""

from datetime import datetime

from pydantic import BaseModel


class RealtimeTicketResponse(BaseModel):
    """One-time WebSocket credential and its authoritative expiration."""

    ticket: str
    expires_at: datetime
