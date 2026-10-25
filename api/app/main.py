from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import APIError, api_error_handler
from app.routers import devices, emergency, health

settings = get_settings()

app = FastAPI(title="FloodGuard Andhra API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(APIError, api_error_handler)

app.include_router(health.router, prefix="/v1")
app.include_router(devices.router, prefix="/v1")
app.include_router(emergency.router, prefix="/v1")
