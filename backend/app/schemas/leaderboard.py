"""API schemas for cumulative game leaderboards."""

from uuid import UUID

from pydantic import BaseModel


class LeaderboardEntryResponse(BaseModel):
    """One ranked active player."""

    rank: int
    player_id: UUID
    display_name: str
    total_score: int


class LeaderboardResponse(BaseModel):
    """Cumulative standings for a game."""

    game_id: UUID
    entries: list[LeaderboardEntryResponse]
