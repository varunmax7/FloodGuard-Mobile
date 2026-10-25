from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

router = APIRouter(tags=["health"])


@router.get("/livez")
async def livez():
    return {"status": "ok", "server_time": datetime.now(timezone.utc).isoformat()}


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok", "server_time": datetime.now(timezone.utc).isoformat()}
