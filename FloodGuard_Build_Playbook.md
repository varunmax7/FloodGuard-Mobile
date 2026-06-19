# FloodGuard — Production Build Playbook (Agent Orchestration Edition)

> **Codename:** FG-MVP-HYD
> **Owner:** Team FG · FloodGuard Solutions Pvt. Ltd.
> **Target:** Real-time urban flood alert system for Hyderabad (Flutter app + Django/PostGIS backend + React admin)
> **How to use this file:** Each **Phase** below is a self-contained work order. Paste **one phase at a time** into Antigravity / Claude Code. Do **not** skip ahead — every phase consumes artifacts produced by the previous one and ends with a `NEXT` block that primes the following agent run.

---

## 0. How This Playbook Is Wired

### 0.1 Orchestration Model

```
                ┌─────────────────────────────────────────────┐
                │  YOU (Human Orchestrator)                    │
                │  - feed one phase per run                    │
                │  - run the Definition-of-Done gate          │
                │  - commit + tag before next phase           │
                └───────────────┬─────────────────────────────┘
                                │  phase prompt + repo state
                ┌───────────────▼─────────────────────────────┐
                │  EXECUTOR AGENT  (Claude Code / Antigravity) │
                │  role rotates per phase (see "Agent" field)  │
                └───────────────┬─────────────────────────────┘
                                │  produces artifacts + CONTRACT.md update
                                ▼
                       [ git commit + tag pNN ]
```

**Rules the executor agent must obey every phase**
1. Read `/CONTRACT.md` first. It is the single source of truth for API shapes, env vars, and data models agreed in earlier phases.
2. Never invent an API contract that contradicts `/CONTRACT.md`. If a change is needed, update `/CONTRACT.md` in the same commit and call it out under `### Contract Changes` at the end of your output.
3. Touch only the files listed in the phase's **Scope**. If you must touch more, list them under `### Scope Deviations`.
4. End every run by printing the phase's **Definition of Done** checklist with ✅/❌ per item, and the `NEXT` handoff line.
5. Output is code + tests + a 5-line run log. No prose essays.

### 0.2 Agent Role Map

| Role tag | Best agent | Phases |
|---|---|---|
| `BACKEND` | Claude Code (terminal, has shell + migrations) | 1–4, 11–12 |
| `MOBILE` | Antigravity / Claude Code | 5–9 |
| `FRONTEND` | Antigravity / Claude Code | 10–12 |
| `DEVOPS` | Claude Code (terminal) | 0, 13 |

### 0.3 Definition-of-Done Gate (run after EVERY phase)
- [ ] App/service builds with zero errors.
- [ ] All new tests pass (`make test` per package).
- [ ] `CONTRACT.md` reflects any new/changed endpoint or model.
- [ ] `git commit -m "pNN: <summary>" && git tag pNN`.
- [ ] The phase's own DoD list is 100% ✅.

---

## 1. Final Tech Stack (locked)

### Mobile app
| Concern | Choice | Why |
|---|---|---|
| Framework | **Flutter 3.24+ / Dart 3** | Single codebase, team's established stack |
| State mgmt | **Riverpod 2 (codegen)** | Testable, no BuildContext coupling |
| Maps | **MapLibre GL (`maplibre_gl`)** | Free vector tiles, GeoJSON hex + raster radar layers |
| Routing | **go_router** | Declarative, deep-linkable for alert taps |
| Local DB / offline | **Drift (SQLite)** | Offline report queue + risk cache |
| Networking | **Dio + Retrofit + json_serializable** | Typed clients |
| Auth | **Firebase Auth (phone OTP)** | Password-less per spec |
| Push | **Firebase Cloud Messaging** | Spec requires FCM delivery receipts |
| Location/permissions | **geolocator, permission_handler** | GPS auto-fill |
| Media | **image_picker, flutter_image_compress** | One-photo reports |
| Background sync | **workmanager** | Offline → online report flush |

### Backend
| Concern | Choice |
|---|---|
| Framework | **Django 5 + Django REST Framework** |
| DB | **PostgreSQL 16 + PostGIS 3.4** (GeoDjango) |
| Spatial indexing | **H3 (`h3-py`) resolution 9** (~174 m edge) for risk hexes |
| Async/queues | **Celery 5 + Redis** (Celery Beat for scheduled ingest) |
| Geodata processing | **rasterio, cfgrib/eccodes, xarray, numpy, shapely, pyproj** |
| Auth (API) | **SimpleJWT**, phone-verified via Firebase Admin SDK token exchange |
| Push dispatch | **firebase-admin** |
| Storage (photos) | **S3-compatible (Cloudflare R2 / AWS S3)** via `django-storages` |

### Admin dashboard
| Concern | Choice |
|---|---|
| Framework | **React 18 + Vite + TypeScript** |
| UI | **TailwindCSS + shadcn/ui** |
| Maps | **MapLibre GL JS** |
| Charts | **Recharts** |
| Data | **TanStack Query + Axios** |
| Auth | **JWT (Admin/Operator/Viewer roles)** |

### Infra / DevOps
- **Docker + docker-compose** (postgis, redis, web, worker, beat).
- **Railway** primary deploy target (team familiarity); R2 for media.
- **GitHub Actions**: lint + test on PR, build images on tag.

### Repo layout (monorepo)
```
floodguard/
├── CONTRACT.md                 # single source of truth (API + models)
├── docker-compose.yml
├── backend/                    # Django + DRF + Celery
├── mobile/                     # Flutter app
├── admin/                      # React admin dashboard
└── infra/                      # CI, deploy, env templates
```

---

## 2. Design System (extracted from approved UI)

> Hand this section verbatim into every MOBILE/FRONTEND phase. Pixel parity with the mockups is a hard requirement.

### Color tokens
| Token | Hex | Use |
|---|---|---|
| `brand/navy-900` | `#0B2545` | Header gradient top, app bars |
| `brand/navy-700` | `#13315C` | Header gradient bottom |
| `brand/blue-600` | `#2563EB` | Primary buttons, active nav, links |
| `risk/low` | `#22C55E` | Green |
| `risk/moderate` | `#FACC15` | Yellow |
| `risk/high` | `#F97316` | Orange |
| `risk/severe` | `#EF4444` | Red |
| `surface/white` | `#FFFFFF` | Cards |
| `surface/glass` | `rgba(255,255,255,0.85)` + blur 12 | Map legend / overlays |
| `text/primary` | `#0F172A` | Headings |
| `text/muted` | `#64748B` | Secondary text |
| `alert/severe-bg` | `#FEF2F2` | Severe alert card bg |

### Typography
- Family: **Inter** (fallback system). H1 22/700, H2 17/600, Body 15/400, Caption 12/500.

### Component spec (must match mockup)
- **App header**: navy vertical gradient, shield+drop logo left, title `FloodGuard` + subtitle `Hyderabad Flood Alert`, bell icon right.
- **Bottom nav (5 tabs)**: Home · Map · Live Radar · Alerts · Report. Active = `brand/blue-600`, inactive = `text/muted`.
- **Risk legend chip**: glass card, 4 colored dots + labels (Low/Moderate/High/Severe).
- **Risk summary**: donut chart (severe/high/moderate/low %), 4-row legend with % area.
- **Report stepper**: 3 steps (Photo → Details → Submit), numbered circles, active filled blue.
- **Cards**: 16px radius, shadow `0 2px 8px rgba(15,23,42,.08)`, 16px padding.
- **Alert cards**: left icon (triangle), risk-tinted; severe uses `alert/severe-bg`.
- Status bar mock `9:41` only on screenshots — not in app.

### Screen inventory (v1 = 5 tabs + report sub-flow)
1. **Home** — overview, today's rain/confidence, risk donut, top hotspots, active-alert banner.
2. **Risk Map** — full-screen H3 risk choropleth, layer toggle (Risk/Radar), location FAB, search.
3. **Live Radar** — animated radar frames, timeline scrubber, intensity legend.
4. **Alerts** — Active / History tabs.
5. **Report Flood** — Photo → Details (depth + road) → Submit (offline-capable), nearby-reports strip.
6. **Settings + Area Detail + Community/Nearby Reports** — supporting screens.

---

## 3. Master Data Contract (seed `/CONTRACT.md` with this in Phase 0)

### 3.1 Core models (backend)
```
HexCell        : h3_index (PK, res9), geom (POLYGON), centroid,
                 fsi_inputs {twi, depression_depth, hand, dist_to_water, slope, imperviousness},
                 fsi_score (0-1, learned weights), ward_name
RiskSnapshot   : hex (FK), ts, rain_1h, rain_3h, rain_24h (forecast, bias-corrected),
                 hazard_class (LOW|MODERATE|HIGH|SEVERE), risk_level (LOW|MODERATE|HIGH|SEVERE),
                 confidence (0-100), source_model ("ECMWF")
AwsStation     : station_id, name, geom (POINT), hex (FK)
AwsObservation : station (FK), ts, rain_1h, rain_3h, rain_24h (observed)
RadarFrame     : ts, tile_url_template, dbz_min, dbz_max, georef_ok (bool)
FloodReport    : id, user (FK,null), geom (POINT), hex (FK), photo_url,
                 depth (ANKLE|KNEE|WAIST|VEHICLE), road (PASSABLE|DIFFICULT|BLOCKED),
                 status (PENDING|VERIFIED|REJECTED|SPAM), observed_at, created_at, client_uuid (idempotency)
User           : id, phone, fcm_token, created_at
SavedPlace     : user (FK), label (HOME|OFFICE|OTHER), geom (POINT), hex (FK), notify (bool)
AlertEvent     : id, hex/area, risk_level, window_start, window_end, message
AlertDelivery  : alert (FK), user (FK), sent_at, delivered_at (FCM receipt), status
BiasFactor     : station/region, multiplier, offset, valid_from, computed_at
CalibrationLog : actor, change_type, before, after, ts   # audit
ModerationLog  : actor, report (FK), action, ts           # audit
```

### 3.2 Risk engine definition (authoritative)
```
hazard_class = bucket(rain_corrected_mm_per_h):
    LOW < 7.5 ≤ MODERATE < 35 ≤ HIGH < 64.5 ≤ SEVERE     # IDF-tunable in admin
rain_corrected = rain_raw * bias.multiplier + bias.offset
risk_level = RISK_MATRIX[hazard_class][susceptibility_bucket(fsi_score)]
    susceptibility_bucket: fsi<0.33 LOW, <0.66 MED, else HIGH
confidence = f(model_agreement, station_density_nearby, forecast_lead_time)
```

### 3.3 Public API (mobile) — base `/api/v1`
```
POST  /auth/otp/request           {phone}                       -> {request_id}
POST  /auth/otp/verify            {request_id, code, fcm_token}  -> {access, refresh, user}
GET   /risk/hexes?bbox=&ts=                                      -> GeoJSON FeatureCollection (risk_level per hex)
GET   /risk/location?lat=&lng=                                  -> {risk_level, plain_text, hourly[24]{ts,risk_level}, explanation, confidence}
GET   /risk/overview                                            -> {forecast_rain_24h, max_rate_1h, confidence, summary{severe,high,moderate,low %}, hotspots[]}
GET   /radar/frames?since=                                      -> [{ts, tile_url_template, intensity_legend}]
POST  /reports            (multipart: photo, lat, lng, depth, road, observed_at, client_uuid) -> FloodReport
GET   /reports/nearby?lat=&lng=&radius_m=1000&since_min=60      -> [FloodReport public fields]
GET   /places                                                  -> [SavedPlace]
POST  /places            {label, lat, lng, notify}             -> SavedPlace
PATCH /places/{id}       {notify}                              -> SavedPlace
GET   /alerts?scope=active|history                             -> [AlertEvent for user's places/location]
POST  /devices/token     {fcm_token}                           -> 204
```

### 3.4 Admin API — base `/api/v1/admin` (JWT, role-gated)
```
GET  /verify/stations/{id}/timeseries?window=72h  -> predicted vs observed series
GET  /verify/errors?metric=mae|bias|corr           -> per-station metrics + trend
GET  /verify/error-map?ts=                          -> hex (predicted-observed) GeoJSON
GET  /validate/reports-vs-risk?from=&to=            -> reports + active risk overlay
GET  /validate/confusion?from=&to=                  -> confusion matrix counts
GET  /validate/hotspot-ranking                      -> areas by agreement/disagreement
GET/PUT /calibrate/weights                          -> FSI weights + matrix thresholds (+preview)
POST /calibrate/backtest        {date}              -> replayed risk vs known flooded localities
GET  /health/feeds                                  -> last ingest ts per feed + stale flags
GET  /health/stations                               -> uptime map
GET  /moderation/queue                              -> pending reports
POST /moderation/{id}/action   {action}             -> verify|reject|spam
GET  /analytics/alerts                              -> sent vs delivered by area/level
GET  /export?type=risk|reports&from=&to=&fmt=csv|geojson
```

---

# PHASES

## Phase 0 — Monorepo Scaffold & Infra `[DEVOPS]`

**Objective:** Stand up the empty-but-runnable monorepo so every later phase has a home and `docker compose up` works.

**Inputs:** None (greenfield).

**Scope (create only):**
```
floodguard/CONTRACT.md            # seed from §3 of this playbook verbatim
floodguard/README.md
floodguard/docker-compose.yml      # services: db(postgis), redis, web, worker, beat
floodguard/.env.example
floodguard/infra/github/ci.yml
floodguard/backend/   (django project "floodguard", apps placeholder, requirements.txt, Dockerfile, Makefile)
floodguard/mobile/    (flutter create, folders: lib/{core,data,features,design})
floodguard/admin/     (vite react-ts scaffold, tailwind + shadcn init)
```

**Tasks**
1. `git init`; add `.gitignore` for python/flutter/node.
2. Backend: Django project + apps stubs `geo, risk, ingest, reports, accounts, alerts, adminapi`. Add DRF, SimpleJWT, Celery, GeoDjango, `h3`, `rasterio`, `cfgrib`, `firebase-admin`, `django-storages`.
3. `docker-compose.yml`: `postgis/postgis:16-3.4`, `redis:7`, `web` (Django runserver), `worker` (celery), `beat`. Healthchecks + volume for DB.
4. Seed `CONTRACT.md` with §3 tables/endpoints exactly.
5. Mobile: `flutter create`, add deps from §1, set up `flavor` (dev/prod) + `--dart-define` for API base URL.
6. Admin: Vite React-TS + Tailwind + shadcn + TanStack Query + MapLibre GL JS + Recharts installed; blank routed shell.
7. CI: lint+test stub jobs for all three packages.

**Definition of Done**
- [ ] `docker compose up` brings db+redis+web+worker+beat to healthy.
- [ ] `flutter run` opens a blank themed app on device/emulator.
- [ ] `npm run dev` in `admin/` serves a blank shell.
- [ ] `CONTRACT.md` committed with full §3 content.
- [ ] Tag `p0`.

**NEXT →** Phase 1 builds the geospatial data layer (PostGIS + H3 hex grid + all models from `CONTRACT.md §3.1`).

---

## Phase 1 — Geo Data Layer: PostGIS, H3 Grid & Models `[BACKEND]`

**Objective:** Create every DB model from `CONTRACT.md §3.1`, generate the Hyderabad H3 res-9 hex grid, and load FSI input rasters into hex attributes.

**Inputs:** Phase 0 repo. Read `CONTRACT.md §3.1, §3.2`.

**Scope:** `backend/geo/`, `backend/risk/models.py`, `backend/accounts/models.py`, `backend/reports/models.py`, `backend/alerts/models.py`, migrations, management commands.

**Tasks**
1. Implement all models per §3.1 with GeoDjango fields + spatial indexes (`GIST`).
2. `manage.py build_hexgrid --bbox <HYD bbox>`: polyfill Hyderabad GHMC boundary at H3 res 9, create `HexCell` rows with geom + centroid.
3. `manage.py load_fsi --layers <dir>`: sample TWI / HAND / slope / imperviousness / depression-depth / distance-to-water rasters into each hex (`rasterstats`/`rasterio`), normalize 0–1, store in `fsi_inputs`, compute `fsi_score` with default equal weights (weights overridable later in Phase 12).
4. Admin-register models for inspection. Add `pytest` + `pytest-django` + factory for HexCell.
5. Index `RiskSnapshot(hex, ts)`, `FloodReport(hex, created_at)`, `AwsObservation(station, ts)`.

**Data contract output:** none new — confirms §3.1 in code.

**Definition of Done**
- [ ] `migrate` clean; PostGIS extensions enabled.
- [ ] `build_hexgrid` produces N>0 hexes covering GHMC; visible in Django admin geo widget.
- [ ] `load_fsi` populates `fsi_score` for ≥95% of hexes (rest flagged).
- [ ] Tests: hex polyfill count sanity + fsi range [0,1]. All green.
- [ ] Tag `p1`.

**NEXT →** Phase 2 adds phone-OTP auth + saved places API so the app can authenticate and personalize.

---

## Phase 2 — Auth (Phone OTP) & Saved Places API `[BACKEND]`

**Objective:** Password-less phone auth via Firebase token exchange → JWT, plus saved-place + device-token endpoints.

**Inputs:** Phase 1 models. Read `CONTRACT.md §3.3 (/auth, /places, /devices)`.

**Scope:** `backend/accounts/` (views, serializers, urls), Firebase Admin init, settings (SimpleJWT, CORS).

**Tasks**
1. Init `firebase-admin` with service-account env. Endpoint flow: client does Firebase phone OTP → sends Firebase ID token to `/auth/otp/verify`; backend verifies token, upserts `User` by phone, returns SimpleJWT `access`/`refresh` + stores `fcm_token`.
   - (Keep `/auth/otp/request` as a thin passthrough/no-op if OTP is fully client-side via Firebase; document the chosen flow in `CONTRACT.md`.)
2. CRUD `/places` (auth required) — on create, snap to `hex` via H3 `latlng_to_cell`. `PATCH` toggles `notify`.
3. `/devices/token` updates `fcm_token`.
4. Throttling on auth endpoints. Tests for verify→JWT, place create snaps to correct hex.

**Definition of Done**
- [ ] Valid Firebase token → JWT pair; invalid → 401.
- [ ] Saved place persists with correct `hex`; `notify` toggles.
- [ ] Tests green; `CONTRACT.md` auth flow note updated.
- [ ] Tag `p2`.

**NEXT →** Phase 3 builds the ingestion pipeline (ECMWF + TGDPS AWS + radar) feeding the risk engine.

---

## Phase 3 — Data Ingestion Pipeline `[BACKEND]`

**Objective:** Scheduled Celery tasks that pull forecast (ECMWF GRIB), observations (TGDPS AWS), and radar frames, normalize them, and write to DB keyed by hex.

**Inputs:** Phases 1–2. Read `CONTRACT.md §3.1` (AwsStation/Observation, RadarFrame), `§3.2` bias-correction note.

**Scope:** `backend/ingest/` (tasks, parsers, celery beat schedule), `backend/risk/models.py` (RiskSnapshot writes deferred to Phase 4).

**Tasks**
1. **ECMWF**: task downloads GRIB for HYD bbox → `cfgrib`/`xarray` → regrid/sample total precip to each `HexCell` centroid → stage forecast accumulations (1h/3h/24h) per hex+ts. (Mock fetch with a fixture file behind a `SETTINGS.INGEST_MOCK` flag so the pipeline runs without live creds.)
2. **TGDPS AWS**: task fetches station rainfall → upsert `AwsObservation`; auto-create `AwsStation` + snap to hex.
3. **Radar**: task fetches latest radar frame metadata → store `RadarFrame` with tile URL template + dBZ range; add a `georef_ok` sanity check (legend/extent validation) and an anomaly flag on weird dBZ distributions.
4. **Bias factor scaffolding**: compute per-station/region `BiasFactor` from (observed vs predicted) over trailing window; store. (Applied in Phase 4.)
5. Celery Beat schedule: ECMWF hourly, AWS 15-min, radar 10-min, bias recompute hourly.
6. **Idempotency + staleness**: each task records last-success ts; tests with fixtures.

**Definition of Done**
- [ ] `celery -A floodguard worker` + `beat` run all 4 tasks against fixtures with zero errors.
- [ ] Forecast staged per hex; observations + radar rows created; bias factors computed.
- [ ] Last-success timestamps recorded (consumed by admin health in Phase 12).
- [ ] Tests green; tag `p3`.

**NEXT →** Phase 4 turns staged feeds into per-hex `RiskSnapshot`s and exposes the public risk/radar APIs.

---

## Phase 4 — Risk Engine & Public Risk/Radar APIs `[BACKEND]`

**Objective:** Compute bias-corrected hazard → risk per hex on a schedule and serve all read endpoints the app needs.

**Inputs:** Phases 1–3. Read `CONTRACT.md §3.2` (engine), `§3.3` (/risk/*, /radar/*).

**Scope:** `backend/risk/` (engine.py, tasks.py, views, serializers, urls), GeoJSON serialization.

**Tasks**
1. `engine.compute_risk(hex, forecast, bias, fsi_score)` implementing §3.2 exactly: bias-correct rain → hazard_class → risk_matrix × susceptibility bucket → `RiskSnapshot` with `confidence`.
2. Celery task `recompute_all_risk()` (runs after ECMWF ingest) writing latest `RiskSnapshot` per hex.
3. Endpoints:
   - `GET /risk/hexes?bbox&ts` → GeoJSON (only hexes in bbox; latest or given ts). Cache 60s.
   - `GET /risk/location?lat&lng` → snap to hex, return current + 24×hourly strip + plain-language text + explanation + confidence.
   - `GET /risk/overview` → city aggregates (rain 24h, max 1h rate, confidence, % area per risk level, top hotspots).
   - `GET /radar/frames?since` → frame list with tile URL template + intensity legend.
4. Plain-language generator: map (risk_level, rain) → strings like "Heavy rain expected — High risk".
5. Performance: bbox query uses GIST; GeoJSON kept lean (risk_level + h3 only).

**Definition of Done**
- [ ] `recompute_all_risk` writes a `RiskSnapshot` for every hex with valid inputs.
- [ ] All 4 endpoints return correct shapes per `CONTRACT.md`; bbox filtering works; <300ms warm.
- [ ] Engine unit tests cover each hazard bucket + matrix cell + bias application.
- [ ] Tag `p4`.

**NEXT →** Phase 5 starts the Flutter app: design-system, theming, routing, API client, and the 5-tab shell wired to live endpoints.

---

## Phase 5 — Flutter Shell: Design System, Routing & API Client `[MOBILE]`

**Objective:** Build the app skeleton — exact theme from §2, go_router 5-tab scaffold, Dio/Retrofit client, Riverpod providers, Drift DB — with the Home screen rendering live data from `/risk/overview`.

**Inputs:** Phase 4 live endpoints. Read §2 (Design System) + `CONTRACT.md §3.3`.

**Scope:** `mobile/lib/design/` (tokens, theme, widgets), `mobile/lib/core/` (router, network, providers), `mobile/lib/data/` (models, api), `mobile/lib/features/home/`.

**Tasks**
1. **Design tokens** → `AppColors`, `AppTextStyles`, `AppTheme` matching §2 hex values + Inter. Build reusable widgets: `FgAppHeader` (navy gradient + logo + bell), `FgBottomNav` (5 tabs), `FgCard`, `RiskDot`, `RiskLegend`, `RiskDonut`, `AlertCard`, `Stepper3`.
2. **Routing** (go_router): `/home /map /radar /alerts /report` + sub-routes `/area/:h3`, `/settings`, `/reports/nearby`. Deep link `/alerts?focus=:h3`.
3. **Network**: Dio + auth interceptor (JWT refresh), Retrofit `FloodGuardApi` typed to §3.3, `json_serializable` models for every response shape.
4. **Drift**: tables for cached risk overview, cached hexes, and an outbox `PendingReport` (used Phase 8).
5. **Home screen** (matches mockup): active-alert banner, "Today's Overview" (forecast rain 24h, max 1h rate, confidence chip), risk donut + % legend, "Top High Risk Areas" list — all from `/risk/overview`. Loading/skeleton + error states.

**Definition of Done**
- [ ] App matches Home mockup pixel-close (header, donut, cards, bottom nav).
- [ ] Home pulls live `/risk/overview`; offline shows cached snapshot.
- [ ] All 5 tabs navigable (placeholders for 2–5).
- [ ] Tag `p5`.

**NEXT →** Phase 6 builds the Risk Map (H3 choropleth) with the Risk/Radar layer toggle and location FAB.

---

## Phase 6 — Risk Map Screen `[MOBILE]`

**Objective:** Full-screen MapLibre map of Hyderabad with the H3 risk choropleth, layer toggle (Risk **or** Radar), "My Location", and search.

**Inputs:** Phase 5 shell. Endpoints `/risk/hexes`, `/radar/frames`, `/risk/location`.

**Scope:** `mobile/lib/features/map/`.

**Tasks**
1. MapLibre GL map centered on HYD; free vector basemap style.
2. **Risk layer**: fetch `/risk/hexes?bbox` on move-end (debounced), render as GeoJSON fill layer colored by `risk_level` (§2 risk tokens, ~0.55 opacity). Re-query on pan/zoom.
3. **Layer toggle** (Risk | Radar, mutually exclusive) — Radar mode swaps in raster layer from `/radar/frames` latest frame.
4. **Glass risk legend** chip (bottom-left) per §2.
5. **"My Location" FAB** → recenter + bottom card showing current risk in plain language from `/risk/location`.
6. **Search bar** → geocode (MapLibre/Nominatim) → fly-to + query that location.
7. Tap on map hex → push `/area/:h3` (screen built in Phase 7).

**Definition of Done**
- [ ] Risk choropleth renders & updates on pan; colors match tokens.
- [ ] Toggle switches Risk↔Radar cleanly (never both).
- [ ] My-Location card shows plain-language current risk.
- [ ] Tap hex routes to Area Detail. Tag `p6`.

**NEXT →** Phase 7 builds Area Detail with the 24h color strip, explanation, and nearby community reports.

---

## Phase 7 — Area Detail & Nearby Reports `[MOBILE]`

**Objective:** The tap-through detail screen: current risk + 24h hour-by-hour color strip, one-line explanation, and nearby reports scoped by radius+time.

**Inputs:** Phase 6. Endpoints `/risk/location`, `/reports/nearby`.

**Scope:** `mobile/lib/features/area_detail/`, shared `ReportCard`, `HourlyRiskStrip` widgets.

**Tasks**
1. Header: area/hex name + current risk badge.
2. **HourlyRiskStrip**: 24 cells colored by hourly `risk_level` (NOT a chart) per spec.
3. One-line explanation text (e.g. "Low-lying area, heavy rain forecast") from API.
4. **Nearby reports**: `/reports/nearby?lat&lng&radius_m=1000&since_min=60`, default last 1h with one-tap extend to 6h/24h. Each card: photo, depth category, road status, time-ago.
5. Empty/loading states; pull-to-refresh.

**Definition of Done**
- [ ] 24h strip renders with correct per-hour colors.
- [ ] Nearby reports filter by radius+time; extend toggles 1h/6h/24h.
- [ ] Matches mockup layout. Tag `p7`.

**NEXT →** Phase 8 builds the offline-first Report Flooding flow (Photo → Details → Submit) with sync queue.

---

## Phase 8 — Report Flooding (Offline-First) `[MOBILE]`

**Objective:** 3-step report flow that works offline and syncs when back online, with pre-submit nearby-reports context.

**Inputs:** Phases 5,7. Endpoint `POST /reports`, `GET /reports/nearby`. Drift outbox from Phase 5.

**Scope:** `mobile/lib/features/report/`, `workmanager` setup.

**Tasks**
1. **Stepper (Photo → Details → Submit)** per mockup.
   - Step 1 Photo: camera/gallery, compress, preview, retake.
   - Step 2 Details: GPS auto-fill (draggable pin to correct), depth (Ankle/Knee/Waist+/Vehicle), road (Passable/Difficult/Blocked), observed-at editable.
   - Step 3 Submit: success screen ("Thank you!").
2. **Nearby strip at top** of report screen: reports within ~1km/last 1h (thumbnail, depth, time-ago) to cut duplicates. Radius/time constants centralized for later tuning.
3. **Offline-first**: write to Drift `PendingReport` with `client_uuid` (idempotency); WorkManager flushes outbox to `POST /reports` on connectivity; UI shows "queued → synced".
4. Permissions (camera, location) handled gracefully.

**Definition of Done**
- [ ] Full flow completes online → server row created.
- [ ] Airplane mode: report queues, then auto-syncs on reconnect (no dupes via `client_uuid`).
- [ ] Nearby strip shows context pre-submit. Matches mockups. Tag `p8`.

**NEXT →** Phase 9 wires Alerts (FCM push + Active/History) and Settings (saved places, phone login).

---

## Phase 9 — Alerts, Settings & Push `[MOBILE]` + `[BACKEND]`

**Objective:** End-to-end push alerts when risk rises at the user's location or saved places, the Alerts screen (Active/History), and Settings (saved places + phone-only login).

**Inputs:** Phases 2,4,5. Endpoints `/alerts`, `/places`, `/devices/token`, `AlertEvent/AlertDelivery` models.

**Scope:** backend `alerts/` (dispatch task + endpoints), mobile `features/alerts/`, `features/settings/`, `features/auth/` (Firebase phone OTP UI).

**Tasks**
- **Backend:** Celery task `dispatch_alerts()` after risk recompute — for hexes that crossed into HIGH/SEVERE, find users with location/saved-place in those hexes (with `notify=true`), create `AlertEvent` + send FCM, record `AlertDelivery` (store FCM receipt → delivered_at). Expose `/alerts?scope=active|history`.
- **Mobile:**
  1. FCM setup (foreground/background/terminated handlers); tap → deep link `/alerts?focus=:h3` → Area Detail.
  2. Alerts screen: Active / History tabs, alert cards per §2 (severe tinted), "View all on map".
  3. Settings: Home/Office/Other saved places (max 3) with per-place notify toggle; phone-OTP login/logout (Firebase) gating save/report only.

**Definition of Done**
- [ ] Simulated risk rise → real push delivered → tap opens correct Area Detail.
- [ ] Active/History populate from API; severe styling correct.
- [ ] Saved places persist + per-place notify toggles drive alerts.
- [ ] `AlertDelivery` records sent + delivered. Tag `p9`.

**NEXT →** **Mobile app is feature-complete.** Phase 10 starts the React admin dashboard (shell + RBAC).

---

## Phase 10 — Admin Dashboard Shell & RBAC `[FRONTEND]` + `[BACKEND]`

**Objective:** React admin app shell with JWT login, three roles (Admin/Operator/Viewer), routed layout, and the audit-log foundation. Maps to spec §2.8.

**Inputs:** Phase 4 admin API base. Read `CONTRACT.md §3.4`, spec §2.8.

**Scope:** backend `accounts` (admin roles + JWT), `adminapi/` (audit middleware), admin/ React app (auth, layout, routing, TanStack Query, shared map/chart wrappers).

**Tasks**
- **Backend:** add `role` (ADMIN|OPERATOR|VIEWER) to staff users; DRF permission classes; `CalibrationLog`/`ModerationLog` audit writes wired as decorators/signals; admin JWT login endpoint.
- **Frontend:** login page → JWT; persisted auth; role-gated nav. Layout = sidebar (8 sections per spec §2.1–2.8) + topbar. Shared `MapPanel` (MapLibre GL JS) and `Chart` (Recharts) wrappers; Axios client with auth + role-aware UI hiding.

**Definition of Done**
- [ ] Login works; Viewer cannot see calibration routes; Operator cannot mutate calibration.
- [ ] Empty routed pages for all 8 sections render.
- [ ] Audit log records a test calibration + moderation action with actor+ts.
- [ ] Tag `p10`.

**NEXT →** Phase 11 builds the two scientific QA modules: Forecast Verification (§2.1) and Report-vs-Risk Validation (§2.2).

---

## Phase 11 — Admin: Forecast Verification & Validation `[FRONTEND]` + `[BACKEND]`

**Objective:** Implement spec §2.1 (predicted vs observed) and §2.2 (report vs risk) — the core scientific QA + model-validation loop.

**Inputs:** Phases 3,4,8,10. Endpoints `/verify/*`, `/validate/*` (`CONTRACT.md §3.4`).

**Scope:** backend `adminapi/verify.py`, `adminapi/validate.py` + serializers; admin pages `ForecastVerification`, `Validation`.

**Tasks**
- **Backend §2.1:** per-station predicted-vs-observed time series (1h/3h/24h, last 24–72h); error metrics MAE/bias/correlation with trend over season; spatial (predicted−observed) hex GeoJSON at latest ts; current bias-correction factor readout; drill-down to raw GRIB-derived + AWS values per station/time cell.
- **Backend §2.2:** reports overlaid on the risk heatmap active at report time; confusion matrix (predicted Low/Mod/High/Severe × reported, exposing false neg/pos); per-event hour-by-hour timeline with report markers; hotspot accuracy ranking (areas by agree/disagree).
- **Frontend:** §2.1 dual-line station charts + error-metric tables/trend lines + spatial error map + bias readout + drill-down modal. §2.2 side-by-side map, confusion-matrix table, per-event timeline, sortable hotspot ranking.

**Definition of Done**
- [ ] §2.1: station chart overlays two lines; MAE/bias/corr correct vs fixtures; error map renders; drill-down shows raw values.
- [ ] §2.2: confusion matrix counts verified against a seeded event; timeline + ranking work.
- [ ] Tag `p11`.

**NEXT →** Phase 12 finishes admin: Calibration Console, System Health, Moderation, Analytics, Export (§2.3–2.7).

---

## Phase 12 — Admin: Calibration, Health, Moderation, Analytics, Export `[FRONTEND]` + `[BACKEND]`

**Objective:** Ship the remaining operational modules so the team can tune the model and run the system day to day.

**Inputs:** Phases 3,4,9,10,11. Endpoints `/calibrate/*`, `/health/*`, `/moderation/*`, `/analytics/*`, `/export`.

**Scope:** backend `adminapi/{calibrate,health,moderation,analytics,export}.py`; admin pages for each.

**Tasks**
- **§2.3 Calibration Console:** editable FSI weights (TWI, depression depth, HAND, dist-to-water, slope, imperviousness) + risk-matrix thresholds + hazard mm/h cutoffs; **preview** recomputes risk for a historical date before commit; **backtest** button ("replay 14 Oct 2020") vs known flooded localities. Every commit writes `CalibrationLog`.
- **§2.4 System & Data Health:** last-ingest ts per feed (ECMWF/AWS/radar) with stale red-flags (from Phase 3 timestamps); AWS station uptime map; radar frame-gap log + dBZ anomaly flag; API error rate/latency/volume panel.
- **§2.5 Moderation Queue:** pending reports list (photo, fields, location, submitter); one-tap Verify/Reject/Flag-spam (rejected excluded from public map + §2.2 validation); duplicate-detection hint (same loc + close ts). Writes `ModerationLog`.
- **§2.6 Analytics:** alerts sent vs delivered (FCM receipts) by area/level; areas generating most alerts over time; usage stats (active users, report rate, geographic coverage / "dark" areas).
- **§2.7 Historical Query & Export:** filter past risk assessments + reports by area+date; export CSV/GeoJSON (serves GHMC/NDMA ops, insurance loss-validation, ML training extraction).

**Definition of Done**
- [ ] Calibration preview + backtest recompute correctly; commit is audited and changes live risk.
- [ ] Health flags a stale feed in test; moderation actions update public visibility + validation set.
- [ ] Analytics matches seeded delivery data; export produces valid CSV + GeoJSON.
- [ ] Tag `p12`.

**NEXT →** Phase 13 is integration hardening, E2E tests, and deploy.

---

## Phase 13 — Integration, Hardening & Deploy `[DEVOPS]`

**Objective:** Make it production-grade and ship it.

**Inputs:** All prior phases.

**Scope:** `infra/`, CI, env, observability across all three packages.

**Tasks**
1. **E2E**: scripted scenario — ingest fixture storm → risk recompute → app shows risk → user files report (offline→sync) → admin moderates → alert dispatched → delivery recorded → admin validation shows the event.
2. **Security**: secrets via env only; rate limits on public endpoints; S3/R2 signed URLs for photos; CORS locked; DRF throttles; JWT rotation.
3. **Performance**: DB indexes audit; cache `/risk/hexes` + `/risk/overview`; tile/GeoJSON payload size budget.
4. **Observability**: Sentry (mobile+backend+admin), structured logs, Celery task monitoring, health `/livez` `/readyz`.
5. **Deploy**: Railway services (web, worker, beat, postgis, redis) from `docker-compose`; R2 bucket; GitHub Actions builds images + runs migrations on tag; Flutter release builds (Android AAB + iOS); admin static deploy.
6. **Runbook**: `infra/RUNBOOK.md` — restart, replay ingest, rotate keys, incident steps.

**Definition of Done**
- [ ] E2E scenario passes start-to-finish in CI.
- [ ] All services deployed + reachable; mobile release build installs; admin live behind auth.
- [ ] Sentry receiving events; health checks green.
- [ ] `RUNBOOK.md` complete. Tag `v1.0.0`.

---

## Appendix A — Per-Phase Agent Prompt Template

Paste this wrapper around each phase when you hand it to an agent:

```
You are the {ROLE} executor for the FloodGuard MVP. Repo is at HEAD tag p{N-1}.

1. Read /CONTRACT.md fully before writing code. It overrides your assumptions.
2. Implement EXACTLY the phase below. Stay within its Scope.
3. Write code + tests. Run the build and tests; paste the result.
4. Update /CONTRACT.md if any endpoint/model changed, in the same commit.
5. End by printing the phase Definition-of-Done checklist with ✅/❌ each,
   any "### Contract Changes" and "### Scope Deviations", then the NEXT line.

--- PHASE ---
<paste one phase here>
```

## Appendix B — Build Order Dependency Graph

```
p0 ─► p1 ─► p2 ─► p3 ─► p4 ─┬─► p5 ─► p6 ─► p7 ─► p8 ─► p9
                            │
                            └─► p10 ─► p11 ─► p12
                                                  │
        (p9 + p12) ───────────────────────────►  p13 ─► v1.0.0
```
- Backend chain (p1–p4) must finish before mobile (p5+) and admin (p10+) start.
- Mobile (p5–p9) and admin (p10–p12) can run in parallel by two agents once p4 is tagged.
- p9 (alert delivery) and p12 (analytics/moderation) both feed p13's E2E.

## Appendix C — Definition-of-Done Gate (run after every phase, no exceptions)
1. `make test` (or `flutter test` / `npm test`) green for the touched package.
2. Service/app builds and runs (`docker compose up` / `flutter run` / `npm run dev`).
3. `/CONTRACT.md` consistent with code.
4. `git commit -m "pNN: <summary>" && git tag pNN`.
5. Phase DoD checklist 100% ✅ before moving on.
