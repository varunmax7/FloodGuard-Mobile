import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["emergency"])

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "emergency_contacts.json"


@lru_cache
def _load() -> dict:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    data.pop("_note", None)
    return data


@router.get("/emergency")
async def get_emergency():
    response = JSONResponse(content=_load())
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response
