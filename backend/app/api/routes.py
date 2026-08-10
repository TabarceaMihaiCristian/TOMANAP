"""Top-level HTTP route registration."""

from fastapi import APIRouter

from app.api.routers.games import router as games_router
from app.api.routers.health import router as health_router
from app.api.routers.leaderboards import router as leaderboards_router
from app.api.routers.lobbies import router as lobbies_router
from app.api.routers.players import router as players_router
from app.api.routers.rounds import router as rounds_router
from app.api.routers.sessions import router as sessions_router
from app.api.routers.submissions import router as submissions_router
from app.api.routers.websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(games_router)
api_router.include_router(players_router)
api_router.include_router(lobbies_router)
api_router.include_router(sessions_router)
api_router.include_router(rounds_router)
api_router.include_router(submissions_router)
api_router.include_router(leaderboards_router)
api_router.include_router(websocket_router)
