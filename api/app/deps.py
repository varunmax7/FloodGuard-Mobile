import uuid
from datetime import datetime, timezone

from fastapi import Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.config import get_settings
from app.db import get_db
from app.errors import APIError
from app.models import Device
from app.security import hash_device_id

settings = get_settings()


async def get_current_device(
    x_device_id: str = Header(..., alias="X-Device-Id"),
    db: AsyncSession = Depends(get_db),
) -> Device:
    try:
        uuid.UUID(x_device_id)
    except ValueError:
        raise APIError(400, "INVALID_DEVICE_ID", "X-Device-Id must be a UUID.")

    device_hash = hash_device_id(x_device_id, settings.device_hash_key)
    device = (await db.execute(select(Device).where(Device.device_hash == device_hash))).scalar_one_or_none()
    if device is None:
        raise APIError(401, "DEVICE_NOT_REGISTERED", "Call POST /devices/register first.")
    if device.blocked:
        raise APIError(403, "DEVICE_BLOCKED", "This device has been blocked.")

    device.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    return device
