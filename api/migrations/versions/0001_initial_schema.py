"""Initial schema — verbatim from FLOODGUARD_ANDHRA_MVP.md §6.2

Revision ID: 0001
Revises:
Create Date: 2026-10-25

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DDL = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE SCHEMA IF NOT EXISTS andhra;
SET search_path = andhra, public;

CREATE TYPE report_category  AS ENUM ('waterlogging','road_flooding','rising_water','other');
CREATE TYPE report_status    AS ENUM ('received','under_review','verified','rejected');
CREATE TYPE capture_method   AS ENUM ('getusermedia','input_capture');
CREATE TYPE track_point_kind AS ENUM ('observed','forecast');
CREATE TYPE notif_kind       AS ENUM ('verified_hotspot','official_warning');
CREATE TYPE model_name       AS ENUM ('gfs','ecmwf_ifs');

-- ---------- Devices (anonymous) ----------
CREATE TABLE devices (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_hash       bytea NOT NULL UNIQUE,     -- HMAC-SHA256(device_uuid, DEVICE_HASH_KEY)
  first_seen_at     timestamptz NOT NULL DEFAULT now(),
  last_seen_at      timestamptz NOT NULL DEFAULT now(),
  locale            text CHECK (locale IN ('en','te')),
  consent_version   text NOT NULL,
  consent_model_use boolean NOT NULL DEFAULT false,
  blocked           boolean NOT NULL DEFAULT false
);

-- ---------- Clusters ----------
CREATE TABLE report_clusters (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  centroid            geography(Point,4326) NOT NULL,
  radius_m            real NOT NULL DEFAULT 0,   -- max distance member->centroid
  first_report_at     timestamptz NOT NULL,
  last_report_at      timestamptz NOT NULL,
  report_count        integer NOT NULL DEFAULT 0, -- non-rejected, non-duplicate
  unique_device_count integer NOT NULL DEFAULT 0,
  verified_count      integer NOT NULL DEFAULT 0,
  dominant_category   report_category,
  heat_weight         real NOT NULL DEFAULT 0,   -- 0..1, see 8.5 (recomputed every 5 min)
  is_hotspot          boolean NOT NULL DEFAULT false,
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','closed')),
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_clusters_centroid ON report_clusters USING gist (centroid);
CREATE INDEX ix_clusters_active ON report_clusters (status, last_report_at DESC);

-- ---------- Flood reports ----------
CREATE TABLE flood_reports (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_report_id      uuid NOT NULL,
  device_id             uuid NOT NULL REFERENCES devices(id),
  category              report_category NOT NULL,
  note                  text CHECK (char_length(note) <= 280),
  location              geography(Point,4326) NOT NULL,
  location_accuracy_m   real NOT NULL CHECK (location_accuracy_m > 0 AND location_accuracy_m <= 1000),
  location_flag         text NOT NULL CHECK (location_flag IN ('precise','approximate')),
  state_code            text CHECK (state_code IN ('AP','OD','OTHER')),
  district_name         text,
  captured_at_client    timestamptz,
  client_clock_skew_s   integer,
  received_at           timestamptz NOT NULL DEFAULT now(),
  capture_method        capture_method NOT NULL,
  image_key             text NOT NULL,            -- object key; never a URL
  image_sha256          bytea NOT NULL,
  image_phash           bigint NOT NULL,
  image_width           integer NOT NULL,
  image_height          integer NOT NULL,
  image_bytes           integer NOT NULL,
  duplicate_of          uuid REFERENCES flood_reports(id),  -- near-identical photo (8.3)
  cluster_id            uuid REFERENCES report_clusters(id),
  status                report_status NOT NULL DEFAULT 'received',
  status_changed_at     timestamptz NOT NULL DEFAULT now(),
  contains_personal_data boolean NOT NULL DEFAULT false,
  user_agent_family     text,
  app_version           text NOT NULL,
  photo_deleted_at      timestamptz,
  CONSTRAINT uq_client_report UNIQUE (device_id, client_report_id)
);
CREATE INDEX ix_reports_location ON flood_reports USING gist (location);
CREATE INDEX ix_reports_status_time ON flood_reports (status, received_at DESC);
CREATE INDEX ix_reports_cluster ON flood_reports (cluster_id);
CREATE INDEX ix_reports_phash ON flood_reports (image_phash);
CREATE INDEX ix_reports_device_time ON flood_reports (device_id, received_at DESC);

-- ---------- Staff, review, misuse ----------
CREATE TABLE staff_users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         citext UNIQUE NOT NULL,
  display_name  text NOT NULL,
  password_hash text NOT NULL,                 -- argon2id
  role          text NOT NULL CHECK (role IN ('reviewer','admin')),
  active        boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE report_reviews (
  id          bigserial PRIMARY KEY,
  report_id   uuid REFERENCES flood_reports(id),
  cluster_id  uuid REFERENCES report_clusters(id),  -- set when action applied to a whole cluster
  reviewer_id uuid NOT NULL REFERENCES staff_users(id),
  from_status report_status,
  to_status   report_status NOT NULL,
  reason_code text CHECK (reason_code IN (
               'consistent_with_other_reports','consistent_with_rainfall','reviewer_local_knowledge',
               'not_flooding','unclear_photo','inappropriate_content','duplicate',
               'location_implausible','other')),
  comment     text CHECK (char_length(comment) <= 500),
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (report_id IS NOT NULL OR cluster_id IS NOT NULL)
);

CREATE TABLE misuse_reports (
  id          bigserial PRIMARY KEY,
  cluster_id  uuid REFERENCES report_clusters(id),
  report_id   uuid REFERENCES flood_reports(id),
  device_id   uuid REFERENCES devices(id),
  reason      text NOT NULL CHECK (reason IN ('not_flooding','privacy','offensive','other')),
  comment     text CHECK (char_length(comment) <= 500),
  created_at  timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);

CREATE TABLE deletion_requests (
  id          bigserial PRIMARY KEY,
  device_id   uuid NOT NULL REFERENCES devices(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

-- ---------- Forecast runs (grids & frames live on disk; DB holds metadata) ----------
CREATE TABLE forecast_runs (
  id            bigserial PRIMARY KEY,
  model         model_name NOT NULL,
  run_at        timestamptz NOT NULL,          -- model initialisation time (e.g. 2026-10-25 00Z)
  started_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz,
  status        text NOT NULL CHECK (status IN ('running','ok','partial','failed')),
  steps_ok      smallint NOT NULL DEFAULT 0,   -- of 25 (0..72 h every 3 h)
  error         text,
  grid_path     text,                          -- /srv/data/grids/<model>/<run>.npz
  frames_path   text,                          -- s3://<FRAMES_BUCKET>/frames/<model>/<run>/
  UNIQUE (model, run_at)
);

-- ---------- Cyclones (from GDACS) ----------
CREATE TABLE cyclone_events (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  gdacs_event_id  integer NOT NULL UNIQUE,
  name            text,
  alert_level     text,                        -- Green | Orange | Red (GDACS)
  basin_note      text,                        -- e.g. 'Bay of Bengal'
  active          boolean NOT NULL DEFAULT true,
  first_seen_at   timestamptz NOT NULL DEFAULT now(),
  last_polled_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cyclone_episodes (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id         uuid NOT NULL REFERENCES cyclone_events(id) ON DELETE CASCADE,
  gdacs_episode_id integer NOT NULL,
  issued_at        timestamptz NOT NULL,       -- advisory time as stated by source
  source_agency    text NOT NULL,              -- e.g. 'JTWC' as given in the record
  max_wind_kmh     real,
  raw_payload      jsonb NOT NULL,             -- unmodified GDACS response for audit
  cone             geography(MultiPolygon,4326), -- only if supplied
  fetched_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_id, gdacs_episode_id)
);

CREATE TABLE cyclone_track_points (
  id          bigserial PRIMARY KEY,
  episode_id  uuid NOT NULL REFERENCES cyclone_episodes(id) ON DELETE CASCADE,
  kind        track_point_kind NOT NULL,
  valid_at    timestamptz NOT NULL,
  position    geography(Point,4326) NOT NULL,
  wind_kmh    real,
  category_label text,                         -- source's own label, shown as-is
  seq         smallint NOT NULL,
  UNIQUE (episode_id, seq)
);

-- ---------- Push ----------
CREATE TABLE push_subscriptions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id       uuid NOT NULL REFERENCES devices(id),
  endpoint        text NOT NULL UNIQUE,
  p256dh          text NOT NULL,
  auth            text NOT NULL,
  area            geography(Point,4326) NOT NULL,   -- rounded to 0.01 degrees
  radius_m        integer NOT NULL DEFAULT 5000 CHECK (radius_m BETWEEN 1000 AND 10000),
  wants_community boolean NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now(),
  disabled_at     timestamptz
);
CREATE INDEX ix_push_area ON push_subscriptions USING gist (area) WHERE disabled_at IS NULL;

CREATE TABLE notification_events (
  id          bigserial PRIMARY KEY,
  kind        notif_kind NOT NULL,
  dedupe_key  text NOT NULL,                   -- 'hotspot:<cluster_id>'
  cluster_id  uuid REFERENCES report_clusters(id),
  title_en    text NOT NULL,
  body_en     text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
-- date_trunc(text, timestamptz) is STABLE (timezone-dependent), not
-- IMMUTABLE, so Postgres refuses it directly in an index expression.
-- Fixed-UTC wrapper below is the standard workaround; same hour-bucket intent.
CREATE OR REPLACE FUNCTION andhra.hour_bucket_utc(ts timestamptz) RETURNS timestamptz AS
$$ SELECT date_trunc('hour', ts AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' $$
LANGUAGE sql IMMUTABLE;

CREATE UNIQUE INDEX uq_notif_dedupe_6h ON notification_events (dedupe_key, andhra.hour_bucket_utc(created_at));

CREATE TABLE notification_deliveries (
  event_id        bigint NOT NULL REFERENCES notification_events(id),
  subscription_id uuid NOT NULL REFERENCES push_subscriptions(id),
  sent_at         timestamptz NOT NULL DEFAULT now(),
  result          text NOT NULL,
  PRIMARY KEY (event_id, subscription_id)
);

-- ---------- Places & districts (for names in alerts, EN + TE) ----------
CREATE TABLE districts (
  code        text PRIMARY KEY,                -- e.g. 'AP-NTR'
  state_code  text NOT NULL CHECK (state_code IN ('AP','OD')),
  name_en     text NOT NULL,
  name_te     text NOT NULL,                   -- reviewed Telugu name (DS-9)
  geom        geography(MultiPolygon,4326) NOT NULL
);
CREATE INDEX ix_districts_geom ON districts USING gist (geom);

CREATE TABLE places (
  id          integer PRIMARY KEY,             -- GeoNames id
  name_en     text NOT NULL,
  name_te     text,                            -- from reviewed list or GeoNames alternate names; NULL -> show name_en
  population  integer,
  district_code text REFERENCES districts(code),
  location    geography(Point,4326) NOT NULL
);
CREATE INDEX ix_places_location ON places USING gist (location);

-- ---------- Alerts ----------
CREATE TYPE alert_kind     AS ENUM ('rain_heavy','rain_very_heavy','cyclone','hotspot','official');
CREATE TYPE alert_severity AS ENUM ('info','watch','high','official');
CREATE TYPE alert_status   AS ENUM ('active','superseded','expired','withdrawn');

CREATE TABLE alerts (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code             text NOT NULL UNIQUE CHECK (code ~ '^[A-Z2-7]{8}$'),
  kind             alert_kind NOT NULL,
  severity         alert_severity NOT NULL,
  status           alert_status NOT NULL DEFAULT 'active',
  district_code    text REFERENCES districts(code),
  cluster_id       uuid REFERENCES report_clusters(id),
  cyclone_event_id uuid REFERENCES cyclone_events(id),
  area             geography(Geometry,4326),   -- district polygon, cluster point, or cyclone track buffer
  area_name_en     text NOT NULL,
  area_name_te     text NOT NULL,
  title_en         text NOT NULL,  title_te   text NOT NULL,
  detail_en        text NOT NULL,  detail_te  text NOT NULL,
  share_text_en    text NOT NULL,  share_text_te text NOT NULL,
  source_label_en  text NOT NULL,  source_label_te text NOT NULL,
  key_values       jsonb NOT NULL,             -- e.g. {"min_mm":31,"max_mm":55,"agreement":"agree"}
  source_refs      jsonb NOT NULL,             -- run ids / GDACS episode / cluster id
  template_version text NOT NULL,
  issued_at        timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  valid_until      timestamptz NOT NULL,
  superseded_by    uuid REFERENCES alerts(id),
  withdrawn_reason text,
  share_count      integer NOT NULL DEFAULT 0,
  og_image_key     text                        -- static per-kind image or rendered cyclone map
);
CREATE INDEX ix_alerts_active ON alerts (status, kind, valid_until) WHERE status = 'active';
CREATE INDEX ix_alerts_area ON alerts USING gist (area);

-- ---------- Rate limiting ----------
CREATE TABLE rate_counters (
  bucket       text NOT NULL,
  window_start timestamptz NOT NULL,
  count        integer NOT NULL,
  PRIMARY KEY (bucket, window_start)
);
"""


def upgrade() -> None:
    # exec_driver_sql (not op.execute) — the DDL's comments contain things like
    # `:31` and `s3://...` that SQLAlchemy's text() would otherwise try to
    # parse as bind parameters.
    op.get_bind().exec_driver_sql(DDL)


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DROP SCHEMA IF EXISTS andhra CASCADE;")
