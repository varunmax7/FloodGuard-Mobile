from datetime import datetime

from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    locale: str | None = Field(default=None, pattern="^(en|te)$")
    consent_version: str
    consent_model_use: bool = False


class DeviceRegisterResponse(BaseModel):
    server_time: datetime
    device_registered: bool
