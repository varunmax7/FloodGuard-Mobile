import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.errors import APIError
from app.models import Device
from app.schemas import DeviceRegisterRequest, DeviceRegisterResponse
from app.security import hash_device_id

router = APIRouter(tags=["devices"])
settings = get_settings()


@router.post("/devices/register", response_model=DeviceRegisterResponse)
async def register_device(
    body: DeviceRegisterRequest,
    x_device_id: str = Header(..., alias="X-Device-Id"),
    db: AsyncSession = Depends(get_db),
):
    try:
        uuid.UUID(x_device_id)
    except ValueError:
        raise APIError(400, "INVALID_DEVICE_ID", "X-Device-Id must be a UUID.")

    device_hash = hash_device_id(x_device_id, settings.device_hash_key)
    device = (await db.execute(select(Device).where(Device.device_hash == device_hash))).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if device is None:
        device = Device(
            device_hash=device_hash,
            locale=body.locale,
            consent_version=body.consent_version,
            consent_model_use=body.consent_model_use,
        )
        db.add(device)
    else:
        device.locale = body.locale or device.locale
        device.consent_version = body.consent_version
        device.consent_model_use = body.consent_model_use
        device.last_seen_at = now

    await db.commit()
    return DeviceRegisterResponse(server_time=now, device_registered=True)
