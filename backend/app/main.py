"""FastAPI application entry point."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, auth, dashboard, notifications, scans
from app.core.config import settings

app = FastAPI(title="track_my_subs API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")


@api.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


api.include_router(auth.router)
api.include_router(accounts.router)
api.include_router(scans.router)
api.include_router(dashboard.router)
api.include_router(notifications.router)

app.include_router(api)
