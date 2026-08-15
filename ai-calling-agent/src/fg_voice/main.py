"""ASGI entrypoint. Wires the FastAPI app together — routes are added
by the P1+ phases; P0 only exposes health endpoints so the container
becomes usable in ECS `HEALTHCHECK` from day one."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fg_voice import __version__
from fg_voice.api.routes_gather import router as gather_router
from fg_voice.api.routes_health import router as health_router
from fg_voice.api.routes_media import router as media_router
from fg_voice.api.routes_voice import router as voice_router
from fg_voice.config import get_settings
from fg_voice.obs.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.fg_log_level, service="fg_voice")
    settings.require_production_secrets()
    log.info(
        "fg_voice.starting",
        version=__version__,
        env=settings.fg_env,
        region=settings.fg_region,
        agent_version=settings.fg_agent_version,
    )
    yield
    log.info("fg_voice.stopping")


app = FastAPI(
    title="FloodGuard Voice Agent",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if get_settings().fg_env != "production" else None,
    redoc_url=None,
)

app.include_router(health_router)
app.include_router(voice_router)
app.include_router(media_router)
app.include_router(gather_router)
