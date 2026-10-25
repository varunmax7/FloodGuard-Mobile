"""Runtime settings — env vars per FLOODGUARD_ANDHRA_MVP.md Appendix B."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    database_url: str = "postgresql+asyncpg://floodguard:floodguard@db:5432/floodguard"
    migrator_database_url: str = "postgresql+psycopg://floodguard:floodguard@db:5432/floodguard"
    data_dir: str = "/srv/data"

    s3_endpoint_url: str = "http://minio:9000"
    s3_public_endpoint_url: str = "http://localhost:9010"
    s3_access_key: str = "floodguard"
    s3_secret_key: str = "floodguard-minio-dev"
    photo_bucket: str = "fg-andhra-photos-dev"
    frames_bucket: str = "fg-andhra-frames-dev"

    gfs_bucket_url: str = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"
    ecmwf_source: str = "aws"
    gdacs_base_url: str = "https://www.gdacs.org/gdacsapi/api"
    weather_bbox: str = "76,8,92,24"  # west,south,east,north
    map_style_url: str = "https://tiles.openfreemap.org/styles/liberty"

    device_hash_key: str = "dev-device-hash-key-change-me"
    ip_hash_key: str = "dev-ip-hash-key-change-me"
    session_secret: str = "dev-session-secret-change-me"
    alert_template_version: str = "2026-10-v1"

    public_app_url: str = "http://localhost:5173"
    cors_origin: str = "http://localhost:5173"

    risk_freshness_hours: int = 2

    feature_alerts: bool = True
    feature_alert_sharing: bool = True
    feature_push: bool = False
    feature_official_push: bool = False
    feature_reports_enabled: bool = True
    feature_cyclone: bool = True
    feature_live_map_animation: bool = True
    feature_input_capture_fallback: bool = True

    @property
    def weather_bbox_tuple(self) -> tuple[float, float, float, float]:
        w, s, e, n = (float(x) for x in self.weather_bbox.split(","))
        return w, s, e, n


@lru_cache
def get_settings() -> Settings:
    return Settings()
