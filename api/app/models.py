"""ORM models mirroring FLOODGUARD_ANDHRA_MVP.md §6.2 DDL (schema `andhra`).

The schema itself is created by the raw-SQL Alembic migration
(migrations/versions/0001_initial_schema.py), copied verbatim from the spec.
These models map onto those exact tables/enums (create_type=False /
extend_existing so SQLAlchemy never tries to re-create what the migration
already created) so the rest of the app can use normal ORM queries.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

SCHEMA = "andhra"


def pg_enum(name: str, *values: str) -> Enum:
    return Enum(*values, name=name, schema=SCHEMA, create_type=False, validate_strings=True)


ReportCategory = pg_enum("report_category", "waterlogging", "road_flooding", "rising_water", "other")
ReportStatus = pg_enum("report_status", "received", "under_review", "verified", "rejected")
CaptureMethod = pg_enum("capture_method", "getusermedia", "input_capture")
TrackPointKind = pg_enum("track_point_kind", "observed", "forecast")
NotifKind = pg_enum("notif_kind", "verified_hotspot", "official_warning")
ModelName = pg_enum("model_name", "gfs", "ecmwf_ifs")
AlertKind = pg_enum("alert_kind", "rain_heavy", "rain_very_heavy", "cyclone", "hotspot", "official")
AlertSeverity = pg_enum("alert_severity", "info", "watch", "high", "official")
AlertStatus = pg_enum("alert_status", "active", "superseded", "expired", "withdrawn")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    device_hash: Mapped[bytes] = mapped_column(unique=True, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    locale: Mapped[str | None] = mapped_column(String)
    consent_version: Mapped[str] = mapped_column(String, nullable=False)
    consent_model_use: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)


class ReportCluster(Base):
    __tablename__ = "report_clusters"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    centroid = mapped_column(Geography("POINT", srid=4326), nullable=False)
    radius_m: Mapped[float] = mapped_column(default=0)
    first_report_at: Mapped[datetime] = mapped_column(nullable=False)
    last_report_at: Mapped[datetime] = mapped_column(nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_device_count: Mapped[int] = mapped_column(Integer, default=0)
    verified_count: Mapped[int] = mapped_column(Integer, default=0)
    dominant_category: Mapped[str | None] = mapped_column(ReportCategory)
    heat_weight: Mapped[float] = mapped_column(default=0)
    is_hotspot: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="active")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    reports: Mapped[list["FloodReport"]] = relationship(back_populates="cluster")


class FloodReport(Base):
    __tablename__ = "flood_reports"
    __table_args__ = (
        UniqueConstraint("device_id", "client_report_id", name="uq_client_report"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    client_report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.devices.id"), nullable=False)
    category: Mapped[str] = mapped_column(ReportCategory, nullable=False)
    note: Mapped[str | None] = mapped_column(String(280))
    location = mapped_column(Geography("POINT", srid=4326), nullable=False)
    location_accuracy_m: Mapped[float] = mapped_column(nullable=False)
    location_flag: Mapped[str] = mapped_column(String, nullable=False)
    state_code: Mapped[str | None] = mapped_column(String)
    district_name: Mapped[str | None] = mapped_column(String)
    captured_at_client: Mapped[datetime | None]
    client_clock_skew_s: Mapped[int | None]
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())
    capture_method: Mapped[str] = mapped_column(CaptureMethod, nullable=False)
    image_key: Mapped[str] = mapped_column(Text, nullable=False)
    image_sha256: Mapped[bytes] = mapped_column(nullable=False)
    image_phash: Mapped[int] = mapped_column(BigInteger, nullable=False)
    image_width: Mapped[int] = mapped_column(Integer, nullable=False)
    image_height: Mapped[int] = mapped_column(Integer, nullable=False)
    image_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.flood_reports.id"))
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.report_clusters.id"))
    status: Mapped[str] = mapped_column(ReportStatus, default="received")
    status_changed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    contains_personal_data: Mapped[bool] = mapped_column(Boolean, default=False)
    user_agent_family: Mapped[str | None] = mapped_column(String)
    app_version: Mapped[str] = mapped_column(String, nullable=False)
    photo_deleted_at: Mapped[datetime | None]

    cluster: Mapped[ReportCluster | None] = relationship(back_populates="reports", foreign_keys=[cluster_id])


class StaffUser(Base):
    __tablename__ = "staff_users"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ReportReview(Base):
    __tablename__ = "report_reviews"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.flood_reports.id"))
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.report_clusters.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.staff_users.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(ReportStatus)
    to_status: Mapped[str] = mapped_column(ReportStatus, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String)
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MisuseReport(Base):
    __tablename__ = "misuse_reports"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.report_clusters.id"))
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.flood_reports.id"))
    device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.devices.id"))
    reason: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[datetime | None]


class DeletionRequest(Base):
    __tablename__ = "deletion_requests"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.devices.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None]


class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    __table_args__ = (
        UniqueConstraint("model", "run_at", name="uq_forecast_run"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model: Mapped[str] = mapped_column(ModelName, nullable=False)
    run_at: Mapped[datetime] = mapped_column(nullable=False)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String, nullable=False)
    steps_ok: Mapped[int] = mapped_column(SmallInteger, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    grid_path: Mapped[str | None] = mapped_column(Text)
    frames_path: Mapped[str | None] = mapped_column(Text)


class CycloneEvent(Base):
    __tablename__ = "cyclone_events"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    gdacs_event_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    alert_level: Mapped[str | None] = mapped_column(String)
    basin_note: Mapped[str | None] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_polled_at: Mapped[datetime] = mapped_column(server_default=func.now())

    episodes: Mapped[list["CycloneEpisode"]] = relationship(back_populates="event")


class CycloneEpisode(Base):
    __tablename__ = "cyclone_episodes"
    __table_args__ = (
        UniqueConstraint("event_id", "gdacs_episode_id", name="uq_cyclone_episode"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.cyclone_events.id", ondelete="CASCADE"), nullable=False)
    gdacs_episode_id: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(nullable=False)
    source_agency: Mapped[str] = mapped_column(String, nullable=False)
    max_wind_kmh: Mapped[float | None]
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cone = mapped_column(Geography("MULTIPOLYGON", srid=4326))
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())

    event: Mapped[CycloneEvent] = relationship(back_populates="episodes")
    track_points: Mapped[list["CycloneTrackPoint"]] = relationship(back_populates="episode")


class CycloneTrackPoint(Base):
    __tablename__ = "cyclone_track_points"
    __table_args__ = (
        UniqueConstraint("episode_id", "seq", name="uq_cyclone_track_seq"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.cyclone_episodes.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(TrackPointKind, nullable=False)
    valid_at: Mapped[datetime] = mapped_column(nullable=False)
    position = mapped_column(Geography("POINT", srid=4326), nullable=False)
    wind_kmh: Mapped[float | None]
    category_label: Mapped[str | None] = mapped_column(String)
    seq: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    episode: Mapped[CycloneEpisode] = relationship(back_populates="track_points")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.devices.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    area = mapped_column(Geography("POINT", srid=4326), nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, default=5000)
    wants_community: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    disabled_at: Mapped[datetime | None]


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(NotifKind, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String, nullable=False)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.report_clusters.id"))
    title_en: Mapped[str] = mapped_column(Text, nullable=False)
    body_en: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = {"schema": SCHEMA}

    event_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.notification_events.id"), primary_key=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.push_subscriptions.id"), primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(server_default=func.now())
    result: Mapped[str] = mapped_column(String, nullable=False)


class District(Base):
    __tablename__ = "districts"
    __table_args__ = {"schema": SCHEMA}

    code: Mapped[str] = mapped_column(String, primary_key=True)
    state_code: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    name_te: Mapped[str] = mapped_column(String, nullable=False)
    geom = mapped_column(Geography("MULTIPOLYGON", srid=4326), nullable=False)


class Place(Base):
    __tablename__ = "places"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    name_te: Mapped[str | None] = mapped_column(String)
    population: Mapped[int | None]
    district_code: Mapped[str | None] = mapped_column(ForeignKey(f"{SCHEMA}.districts.code"))
    location = mapped_column(Geography("POINT", srid=4326), nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("code ~ '^[A-Z2-7]{8}$'", name="ck_alert_code"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(AlertKind, nullable=False)
    severity: Mapped[str] = mapped_column(AlertSeverity, nullable=False)
    status: Mapped[str] = mapped_column(AlertStatus, default="active")
    district_code: Mapped[str | None] = mapped_column(ForeignKey(f"{SCHEMA}.districts.code"))
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.report_clusters.id"))
    cyclone_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.cyclone_events.id"))
    area = mapped_column(Geography("GEOMETRY", srid=4326))
    area_name_en: Mapped[str] = mapped_column(Text, nullable=False)
    area_name_te: Mapped[str] = mapped_column(Text, nullable=False)
    title_en: Mapped[str] = mapped_column(Text, nullable=False)
    title_te: Mapped[str] = mapped_column(Text, nullable=False)
    detail_en: Mapped[str] = mapped_column(Text, nullable=False)
    detail_te: Mapped[str] = mapped_column(Text, nullable=False)
    share_text_en: Mapped[str] = mapped_column(Text, nullable=False)
    share_text_te: Mapped[str] = mapped_column(Text, nullable=False)
    source_label_en: Mapped[str] = mapped_column(Text, nullable=False)
    source_label_te: Mapped[str] = mapped_column(Text, nullable=False)
    key_values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    template_version: Mapped[str] = mapped_column(String, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    valid_until: Mapped[datetime] = mapped_column(nullable=False)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.alerts.id"))
    withdrawn_reason: Mapped[str | None] = mapped_column(Text)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    og_image_key: Mapped[str | None] = mapped_column(Text)


class RateCounter(Base):
    __tablename__ = "rate_counters"
    __table_args__ = {"schema": SCHEMA}

    bucket: Mapped[str] = mapped_column(String, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
