"""Runtime configuration for the FloodGuard Voice Agent.

Fails at boot on missing required env vars — never at runtime, and never
with a caller on the line. See CLAUDE.md invariant #7.

Loaded once at process start via `get_settings()`. The result is cached
so imports remain cheap and the object is safely shared across async tasks.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """All runtime settings. Field names mirror .env.example exactly."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Runtime ──────────────────────────────────────────────
    fg_env: Environment = Environment.DEV
    fg_agent_version: str = "dev-local"
    fg_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    fg_region: str = "ap-south-1"

    # ── Telephony ────────────────────────────────────────────
    telephony_provider: Literal["twilio", "exotel"] = "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    twilio_phone_number: str = ""
    twilio_media_region: str = "sg1"
    public_wss_base: str = "wss://voice.floodguard.in"

    # ── STT ──────────────────────────────────────────────────
    deepgram_api_key: SecretStr = SecretStr("")
    stt_model: str = "flux-general-en"
    stt_fallback_model: str = "nova-3"
    stt_eot_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    stt_eager_eot_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    stt_eot_timeout_ms: int = Field(default=1200, ge=100, le=10_000)

    # ── TTS ──────────────────────────────────────────────────
    tts_provider: Literal["cartesia", "deepgram", "polly"] = "cartesia"
    tts_api_key: SecretStr = SecretStr("")
    tts_voice_id: str = ""
    tts_cache_ttl_sec: int = 604_800
    audio_bank_path: Path = Path("./prompts/audio_bank/en-IN")

    # ── LLM ──────────────────────────────────────────────────
    llm_provider: Literal["bedrock", "anthropic"] = "bedrock"
    bedrock_region: str = "ap-south-1"
    llm_model_id: str = ""
    llm_fallback_api_key: SecretStr = SecretStr("")
    llm_timeout_ms: int = Field(default=800, ge=100, le=10_000)
    llm_max_tokens: int = Field(default=100, ge=10, le=1000)

    # ── Noise suppression ────────────────────────────────────
    denoise_provider: Literal["krisp", "rnnoise", "none"] = "rnnoise"
    krisp_license_key: SecretStr = SecretStr("")

    # ── Data ─────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://fg_voice:fg_voice@localhost:55432/fg_voice"
    redis_url: str = "redis://localhost:56379/0"
    caller_hash_pepper: SecretStr = SecretStr("dev-only-do-not-use-in-prod")
    s3_recordings_bucket: str = "fg-voice-recordings"
    s3_transcripts_bucket: str = "fg-voice-transcripts"
    s3_reports_bucket: str = "fg-reports"
    s3_rag_bucket: str = "fg-voice-rag"
    efs_csv_path: Path = Path("./data/csv")
    csv_schema_version: int = 1

    # ── AWS ──────────────────────────────────────────────────
    aws_endpoint_url: str | None = None  # set to localstack URL in dev
    aws_access_key_id: str | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_default_region: str = "ap-south-1"

    # ── RAG ──────────────────────────────────────────────────
    gazetteer_snapshot_version: str = "latest"
    taxonomy_version: str = "latest"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    geo_accept_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    geo_confirm_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    geo_margin_threshold: float = Field(default=0.10, ge=0.0, le=1.0)

    # ── Conversation ─────────────────────────────────────────
    max_call_duration_sec: int = Field(default=300, ge=30, le=1800)
    no_input_timeout_ms: int = Field(default=6000, ge=1000, le=30_000)
    max_attempts_per_slot: int = Field(default=3, ge=1, le=5)
    emergency_number: str = "112"
    # RUNNER_MODE=true → /voice/inbound redirects to the Gather-based
    # HTTP flow instead of the Media Streams path. Provides a keyless
    # bring-up path for the P2 exit gate (Twilio does the STT itself);
    # Media Streams comes back for P3 once Deepgram is wired.
    runner_mode: bool = False
    # RELAY_ENABLED=false disables the outbox relay background task
    # (useful in tests + in workers that only serve HTTP with no DB
    # writes). Defaults to true so a fresh deploy drains its outbox
    # without any extra config.
    relay_enabled: bool = True
    relay_poll_interval_sec: float = Field(default=1.0, ge=0.05, le=60.0)
    # CSV_ENABLED=true adds the CSV projector to the relay's dispatch
    # chain. Off by default so tests + CI don't accumulate files on
    # disk; on in staging/prod where downstream tooling consumes it.
    csv_enabled: bool = False
    csv_path: Path = Path("./data/reports.csv")
    # ALERTS_ENABLED=true adds the alert fan-out dispatcher. The
    # log-backend always fires when enabled; the webhook-backend only
    # when ALERT_WEBHOOK_URL is set. Off by default because a bad
    # webhook config is worse than no alerts (alerts still hit the log).
    alerts_enabled: bool = False
    alert_webhook_url: str = ""
    alert_webhook_timeout_sec: float = Field(default=5.0, ge=0.5, le=30.0)

    # Admin API key for the /api/v1/reports* endpoints. Empty means
    # auth is disabled (dev bypass); production boot logs a warning
    # AND `require_production_secrets` refuses to boot without it set.
    admin_api_key: SecretStr = SecretStr("")

    # ── Ops ──────────────────────────────────────────────────
    alert_sns_topic_arn: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    surge_mode_min_tasks: int = 10

    # ── validators ───────────────────────────────────────────
    @field_validator("caller_hash_pepper")
    @classmethod
    def _reject_dev_pepper_in_prod(cls, v: SecretStr, info) -> SecretStr:  # type: ignore[no-untyped-def]
        env = info.data.get("fg_env")
        if env == Environment.PRODUCTION and v.get_secret_value().startswith("dev-only"):
            raise ValueError(
                "CALLER_HASH_PEPPER cannot use the dev placeholder in production. "
                "Rotate via Secrets Manager before boot."
            )
        return v

    def is_production(self) -> bool:
        return self.fg_env == Environment.PRODUCTION

    def require_production_secrets(self) -> None:
        """Called from main.py at startup when fg_env=production. Any missing
        production-only secret raises here, so a broken deploy never accepts
        traffic."""
        if not self.is_production():
            return
        required: list[tuple[str, str]] = [
            ("twilio_account_sid", self.twilio_account_sid),
            ("twilio_auth_token", self.twilio_auth_token.get_secret_value()),
            ("twilio_phone_number", self.twilio_phone_number),
            ("admin_api_key", self.admin_api_key.get_secret_value()),
            ("deepgram_api_key", self.deepgram_api_key.get_secret_value()),
            ("tts_api_key", self.tts_api_key.get_secret_value()),
            ("tts_voice_id", self.tts_voice_id),
            ("llm_model_id", self.llm_model_id),
            ("alert_sns_topic_arn", self.alert_sns_topic_arn or ""),
        ]
        missing = [name for name, value in required if not value]
        if missing:
            raise RuntimeError(f"Production boot missing required settings: {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Import this, never instantiate Settings directly."""
    return Settings()
