"""Common API schemas.

Define reusable response envelopes, pagination metadata, error payloads,
timestamped models, and shared primitive value objects.
"""

from pydantic import BaseModel, ConfigDict


class StrictRequestModel(BaseModel):
    """Reject unknown fields and implicit coercion at trust boundaries."""

    model_config = ConfigDict(extra="forbid", strict=True)
