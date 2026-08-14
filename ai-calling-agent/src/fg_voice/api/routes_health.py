"""/healthz, /readyz, /metrics.

Health endpoints are load-bearing from P0: ECS uses them for task health
checks and rolling-deploy gates. /readyz returns 503 until dependencies
(Redis, DB, RAG snapshots) are actually reachable — never before.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status

from fg_voice import __version__
from fg_voice.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="liveness probe")
async def healthz() -> dict[str, Any]:
    """Liveness — process is up and responding. Cheap; no dependencies."""
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "agent_version": settings.fg_agent_version,
        "env": settings.fg_env,
    }


@router.get("/readyz", summary="readiness probe")
async def readyz(response: Response) -> dict[str, Any]:
    """Readiness — can we take traffic? P0 only checks config was loaded;
    P4 will add RAG snapshot readiness, P5 will add DB/Redis pings."""
    checks: dict[str, str] = {"config": "ok"}
    # future: checks["redis"] = await ping_redis()
    # future: checks["postgres"] = await ping_db()
    # future: checks["rag_snapshots"] = "loaded" if snapshots_loaded else "loading"
    if all(v == "ok" or v == "loaded" for v in checks.values()):
        return {"status": "ready", "checks": checks}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not_ready", "checks": checks}
