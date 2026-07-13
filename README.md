# FloodGuard

**Real-time urban flood alert system for Hyderabad.**
Flutter mobile app · Django/PostGIS backend · React admin dashboard.

FloodGuard forecasts rainfall down to a ~110 m hex grid across the GHMC area, mixes that with live radar and community reports, and pushes personalised alerts. All live data is pulled from free public sources — no paid weather API.

---

## What's live

| Layer | Source | What it powers |
|---|---|---|
| Rainfall forecast | Open-Meteo Forecast API (free, no key) | 48h hex-level risk, city forecast strip, station observations |
| Precipitation radar | RainViewer public API (free, no key) | Live Radar tab (satellite basemap) + Map screen radar toggle |
| Current conditions | Open-Meteo current weather | Home screen weather chip |
| Reverse geocoding | Apple/Google system geocoder + Nominatim (OSM) fallback | "You are in Madhapur" on Home |
| Auth | Firebase Phone OTP + JWT | Sign-in (dev-mode fallback available) |
| Push | Firebase Cloud Messaging | Alert delivery |

All feeds respect a **stale-forecast contract**: if the upstream feed hasn't reported within `RISK_FRESHNESS_HOURS` (default 2), every `/risk/*` endpoint returns `503 STALE_FORECAST` with a `last_update` timestamp instead of serving cached/seeded values. The mobile app renders a "No live data yet" state rather than lying to users.

## External APIs — what we use and why

FloodGuard has a hard rule: **no paid weather APIs, no vendor lock-in on core data**. Every external API below was picked because it is free, keyless (or nearly so), well-documented, and stable enough to run a public safety product on. Where a paid alternative exists, we note it.

### 1. Open-Meteo Forecast API — rainfall forecast

- **What**: Hourly total precipitation forecast, sampled at the centroid of every H3 res-9 hex in the GHMC area (~13,875 points).
- **Where in code**: `backend/apps/ingest/parsers/ecmwf.py` → `ingest_ecmwf` Celery task → `ForecastStage` → `RiskSnapshot` via `recompute_all_risk`.
- **Why chosen**:
  - **Free and keyless** — no API key, no monthly quota to babysit, no billing surprises during a monsoon spike.
  - **ECMWF-backed** — Open-Meteo aggregates ECMWF IFS and other global models. ECMWF is the gold standard for medium-range precipitation forecasting.
  - **Hex-native** — accepts arbitrary lat/lng, which lets us sample per H3 centroid instead of interpolating from a coarse grid.
  - **Batchable** — one HTTP call can return forecasts for many points, which keeps ingest under the hourly Celery beat cadence.
- **What we'd swap to**: If we ever needed higher-resolution nowcasts, IMD's Meghdoot or a paid nowcast product (Tomorrow.io) — but Open-Meteo's 48h horizon covers our alerting window.

### 2. Open-Meteo Historical / "Weather Now" — current conditions + station observations

- **What**: (a) Current temperature, humidity, wind, description for the Home screen chip. (b) Recent-past rainfall used as pseudo-station observations for bias correction.
- **Where in code**: `backend/apps/ingest/parsers/aws.py` (`ingest_aws`) and `apps/risk/views.py::weather_now`.
- **Why chosen**:
  - **Same vendor as forecast** — one integration surface, one failure mode to monitor.
  - **Fills the AWS gap** — India's live automatic-weather-station (AWS) feed is patchy and requires MoU-level access. Open-Meteo's past-hour observations are a viable substitute for computing forecast-vs-actual bias factors per hex.
  - **Feeds the bias-correction loop** — `recompute_bias` compares observed rain against forecasted rain per station and stores a multiplier back into `BiasFactor`, which the risk engine applies to the next forecast cycle.

### 3. RainViewer — precipitation radar

- **What**: Tile URLs and per-frame metadata for the Live Radar tab and the Map screen radar overlay. 10-minute cadence, 2h history + short nowcast.
- **Where in code**: `backend/apps/ingest/parsers/radar.py`, `ingest_radar`, `apps.radar.models.RadarFrame`, `/api/v1/radar/frames`.
- **Why chosen**:
  - **Free public tiles** — no key, no attribution requirements beyond a small credit.
  - **Global coverage** — works over Hyderabad without needing an IMD DWR feed (which is not publicly available in a machine-readable form).
  - **Client-side rendering** — the tiles are consumed directly by MapLibre GL, so the backend only stores frame timestamps + URLs (cheap).
  - **Nowcast frames included** — RainViewer publishes a short forecast strip, which the mobile Live Radar player can loop past+future in one control.

### 4. OpenStreetMap Nominatim (fallback) + system geocoder — reverse geocoding

- **What**: Turning a GPS coordinate into "You are in Madhapur" on Home + Report screens.
- **Where in code**: Mobile `lib/features/home/home_providers.dart` via `geocoding` plugin (system geocoder first, then Nominatim fallback).
- **Why chosen**:
  - **Zero cost, zero key** — Google Places would give better area names in India but costs per request and requires a billing account.
  - **System geocoder first** — on iOS/Android the OS geocoder is free and offline-capable; Nominatim only kicks in when the OS returns nothing (Flutter Web, some Android OEMs).
  - **Good enough for ward-level display** — we only need neighbourhood-level names, not building-level accuracy.

### 5. Firebase Phone Auth (OTP) — user sign-in

- **What**: SMS OTP verification. The Firebase ID token is exchanged server-side for a SimpleJWT pair (`/api/v1/auth/otp/verify`).
- **Where in code**: Mobile `lib/features/auth/*`, backend `apps/auth/views.py::verify_otp`.
- **Why chosen**:
  - **India SMS delivery works out of the box** — Twilio and MSG91 need business KYC and cost per SMS; Firebase eats that on the free tier for our volumes.
  - **Fraud handling included** — reCAPTCHA + app attestation are free with Firebase; rolling our own would be a security liability.
  - **Dev-mode fallback baked in** — when `FIREBASE_CREDENTIALS_JSON` is empty the backend accepts a fixed dev OTP, which keeps local development and CI unblocked without burning SMS credits.

### 6. Firebase Cloud Messaging — push alerts

- **What**: Fan-out of `HIGH`/`SEVERE` alerts to subscribed devices, plus per-place notifications when a saved location crosses a threshold.
- **Where in code**: `backend/apps/alerts/tasks.py` (dispatch), `mobile/lib/core/messaging/*` (device registration).
- **Why chosen**:
  - **Cross-platform, free** — one API sends to Android, iOS, and Web PWA.
  - **Topic subscriptions** — every hex has a topic; devices subscribe to the hex(es) covering their saved places, so we don't maintain a per-user delivery list.
  - **APNs handled transparently** — no separate Apple Push credential rotation to run.

### 7. Sentry — error tracking

- **What**: Unhandled exceptions and performance traces from backend, admin dashboard, and the mobile app.
- **Where in code**: `backend/floodguard/settings.py::SENTRY_DSN`, `admin/src/main.tsx`, `mobile/lib/main.dart`.
- **Why chosen**:
  - **One dashboard across three runtimes** — Python, JS/TS, and Dart all have first-party SDKs.
  - **Free tier is enough for a single-city product** — we're well under the 5k events/mo cap.
  - **Optional at build time** — leave `SENTRY_DSN` unset and the SDKs no-op; keeps dev quiet.

### API summary matrix

| API | Cost | Key required | Cadence | Fallback if it fails |
|---|---|---|---|---|
| Open-Meteo Forecast | Free | No | Hourly | Serve last good `RiskSnapshot`; after `RISK_FRESHNESS_HOURS` return `503 STALE_FORECAST` |
| Open-Meteo Now | Free | No | 15 min | Weather chip hidden |
| RainViewer | Free | No | 10 min | Radar toggle disabled with a note |
| Nominatim | Free (fair-use) | No | On-demand | System geocoder result; if that's also empty, show raw coordinates |
| Firebase Auth | Free (fair-use) | Yes (server creds) | On login | Dev-mode fixed OTP when creds missing |
| Firebase FCM | Free | Yes (server creds) | On alert | Alert stored in DB; user sees it on next app open |
| Sentry | Free (5k/mo) | Yes (DSN) | Continuous | SDK no-ops when unset |

## Repository layout

```
floodguard/
├── CONTRACT.md              # API contracts, data models, env vars (single source of truth)
├── docker-compose.yml       # Local dev orchestration
├── .env.example             # Copy to .env and fill in secrets
├── backend/                 # Django 5 + DRF + Celery + PostGIS
├── mobile/                  # Flutter 3.24 app (Android + iOS + Web)
├── admin/                   # React 18 + Vite + Tailwind admin dashboard
└── infra/                   # railway.toml, RUNBOOK.md, CI config
```

## Tech stack

| Layer | Technology |
|---|---|
| Mobile | Flutter 3.24, Riverpod 2, MapLibre GL, go_router, Drift, geolocator, geocoding, fl_chart |
| Backend | Django 5, DRF, GeoDjango, PostGIS 3.4, Celery 5, Redis, SimpleJWT |
| Spatial | H3 res-9 (~110 m hexes), shapely |
| Ingest | Open-Meteo, RainViewer (no keys) |
| Auth | Firebase Phone OTP → SimpleJWT exchange |
| Push | Firebase Cloud Messaging |
| Admin | React 18, Vite, TailwindCSS, MapLibre GL JS |
| Observability | Sentry (backend + admin + mobile), `/livez`, `/readyz` |
| Infra | Docker, Railway, Cloudflare R2, GitHub Actions |

## Quickstart

### Prerequisites
- Flutter 3.24+ (`flutter doctor` clean)
- Node.js 20 LTS
- Python 3.13+
- PostgreSQL 16 + PostGIS (local dev) **or** Docker Desktop
- Android Studio / Xcode (for mobile emulator)

### 1. Backend (local Postgres, no Docker)

```bash
# One-time: install PostgreSQL + PostGIS
brew install postgresql@16 postgis
brew services start postgresql@16

# One-time: create DB
psql postgres -c "CREATE USER floodguard WITH PASSWORD 'floodguard';"
psql postgres -c "CREATE DATABASE floodguard OWNER floodguard;"
psql floodguard -c "CREATE EXTENSION postgis;"

# Python deps
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Migrate + seed the hex grid
python manage.py migrate
python manage.py build_hexgrid   # loads ~13,875 H3 hexes over GHMC
python manage.py load_fsi        # loads FSI (Flood Susceptibility Index) per hex
python manage.py createsuperuser

# Start the API
python manage.py runserver 0.0.0.0:8000
# Admin → http://localhost:8000/admin
# Health → http://localhost:8000/api/v1/livez/
```

### 2. Run one live ingest manually (optional)

The Celery beat schedule runs the ingest hourly, but you can prime the DB with real data now:

```bash
DJANGO_SETTINGS_MODULE=floodguard.settings python -c "
import django; django.setup()
from apps.ingest.tasks import ingest_ecmwf, ingest_aws, ingest_radar
from apps.risk.tasks import recompute_all_risk
for t in [ingest_ecmwf, ingest_aws, ingest_radar, recompute_all_risk]:
    r = t.apply()
    print(t.__name__, '->', r.result)
"
```

This pulls live Open-Meteo forecast + station observations + RainViewer radar and computes risk snapshots for every hex.

### 3. Flutter app

```bash
cd mobile
flutter pub get
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

**Device-specific base URLs**: `localhost` works for iOS simulator and Flutter web; use `http://10.0.2.2:8000` for Android emulator, or your machine's LAN IP (e.g. `http://192.168.1.42:8000`) for a real phone.

### 4. Admin dashboard

```bash
cd admin
npm install
npm run dev
# → http://localhost:5173
```

---

## Docker — when you need it

Docker is **not required** for backend/mobile/admin dev. Reach for it when:

| Situation | Why |
|---|---|
| Running Celery worker + beat locally | Redis + worker + beat all in one command |
| Onboarding a teammate | `docker compose up` gives everyone the identical env |
| Production deploy | Railway builds and runs the Docker image |
| CI/CD | GitHub Actions builds and pushes on tag |

```bash
brew install --cask docker
cp .env.example .env
docker compose up -d   # db, redis, web, worker, beat
```

---

## Key public endpoints

Read [CONTRACT.md](./CONTRACT.md) for the full list. Highlights:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/risk/overview` | City summary (metrics, donut, hotspots) |
| `GET /api/v1/risk/location?lat=&lng=` | Per-location risk + ward + 24h strip |
| `GET /api/v1/risk/hexes?bbox=` | GeoJSON choropleth for the Map |
| `GET /api/v1/risk/hourly-forecast` | 48h city rain forecast (Home strip) |
| `GET /api/v1/risk/weather-now` | Current temp/humidity/wind chip |
| `GET /api/v1/radar/frames` | RainViewer tile URLs from DB |
| `GET /api/v1/reports/nearby?lat=&lng=&radius_m=&since_min=` | Community reports around a point |
| `POST /api/v1/reports/` (multipart) | Submit a flood report with photo |
| `GET /api/v1/alerts?scope=active` | Active + past FCM alerts |
| `POST /api/v1/auth/otp/verify` | Firebase OTP → SimpleJWT exchange |
| `GET /api/v1/livez`, `readyz` | Health probes for Railway |

Public risk endpoints return **`503 STALE_FORECAST`** when the upstream feed is stale — mobile treats this as a "no live data yet" state, not a hard error.

## Environment variables

Everything is documented in [CONTRACT.md](./CONTRACT.md). Minimum viable dev `.env`:

```bash
# Backend
DATABASE_URL=postgis://floodguard:floodguard@localhost:5432/floodguard
DJANGO_SECRET_KEY=dev-secret-change-me
DJANGO_DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Feed switches (True → hit real free APIs; False → seeded fixtures)
INGEST_MOCK=True
FORECAST_LIVE=True   # Open-Meteo forecast
AWS_LIVE=True        # Open-Meteo station observations
RADAR_LIVE=True      # RainViewer

# Staleness gate
RISK_FRESHNESS_HOURS=2

# Optional
CACHE_URL=redis://localhost:6379/1     # LocMem fallback if unset
SENTRY_DSN=
FIREBASE_CREDENTIALS_JSON=              # If empty, dev-mode OTP is used
```

## Development phases

| Tag | Phase | Status |
|---|---|---|
| p0 | Monorepo scaffold + infra | ✅ tagged |
| p1 | Geospatial data layer (PostGIS + H3) | ✅ tagged |
| p2 | Auth (phone OTP) + saved places API | ✅ tagged |
| p3 | Ingest pipeline (forecast + stations + radar + bias) | ✅ tagged |
| p4 | Risk engine + public risk/radar APIs | ✅ tagged |
| p5 | Flutter shell — design tokens, routing, API client | ✅ tagged |
| p6 | Risk Map screen (choropleth + toggle + search) | ✅ tagged |
| p7 | Area Detail + Nearby Reports | ✅ tagged |
| p8 | Report Flooding (offline-first) | ✅ shipped |
| p9 | Alerts, Settings, Push | ✅ shipped |
| p10 | Admin shell + RBAC | ✅ tagged |
| p11 | Admin: Forecast Verification + Validation | ✅ tagged |
| p12 | Admin: Calibration, Health, Moderation, Analytics, Export | ✅ tagged |
| p13 | Integration hardening + E2E + deploy config | ✅ tagged |
| v1.0.0 | Real-time feeds + Home rebuild + staleness contract | ✅ tagged |

The `v1.0.0` tag captures the current production-ready state: all three feeds live, Home screen rebuilt with personal risk + weather + forecast strip + nearby reports, backend-to-mobile staleness contract enforced.

## Home screen features

The current Home stack (top to bottom):

1. **Personal risk card** — device GPS → `/risk/location`. Shows your ward/area (reverse-geocoded), risk badge, personalised rain totals, confidence, and jumps to Area Detail.
2. **Weather-now chip** — live temp / humidity / wind / description from Open-Meteo.
3. **48h rain forecast strip** — mini bar chart with intensity colouring; shows peak and total, or "No rain expected".
4. **Nearby community reports** — flood reports within 5 km in the last hour, with severity-tinted accent bar; hidden gracefully when location isn't available.
5. **Alert banner** — only shown when a HIGH/SEVERE hotspot exists.
6. **City overview** — 24h forecast, max 1h rate, confidence.
7. **Risk distribution donut** — % of the city in each risk band.
8. **Top high-risk areas** — ranked list of the worst hexes.

All cards respect the staleness contract: if the upstream feed goes offline they show a friendly "No live data yet" state, not lies.

## Deploy

The `v*` tag triggers three CI jobs: Docker image push to GHCR, Flutter Android AAB build, admin static deploy. Backend runs on Railway (`infra/railway.toml` defines `web` + `worker`).

```bash
# From floodguard/
git push origin main
git push origin v1.0.0   # triggers CI/CD
```

See [`infra/RUNBOOK.md`](./infra/RUNBOOK.md) for restart / replay-ingest / key-rotation / incident runbooks.

## Contract

All API shapes, data models, and env vars live in [CONTRACT.md](./CONTRACT.md). **Read it before writing code.**

## License

Proprietary — FloodGuard Solutions Pvt. Ltd.
