# FloodGuard CONTRACT.md
> **Single source of truth** for API shapes, environment variables, and data models.
> Every phase must read this before writing code. Changes must be called out under `### Contract Changes`.

---

## §3.1 Core Models (Backend)

```
HexCell        : h3_index (PK, res9), geom (POLYGON), centroid,
                 fsi_inputs {twi, depression_depth, hand, dist_to_water, slope, imperviousness},
                 fsi_score (0-1, learned weights), ward_name

RiskSnapshot   : hex (FK→HexCell), ts, rain_1h, rain_3h, rain_24h (forecast, bias-corrected),
                 hazard_class (LOW|MODERATE|HIGH|SEVERE),
                 risk_level  (LOW|MODERATE|HIGH|SEVERE),
                 confidence  (0-100), source_model ("ECMWF")

AwsStation     : station_id, name, geom (POINT), hex (FK→HexCell)

AwsObservation : station (FK→AwsStation), ts,
                 rain_1h, rain_3h, rain_24h  (observed)

RadarFrame     : ts, tile_url_template, dbz_min, dbz_max, georef_ok (bool)

FloodReport    : id, user (FK→User, null), geom (POINT), hex (FK→HexCell),
                 photo_url,
                 depth (ANKLE|KNEE|WAIST|VEHICLE),
                 road  (PASSABLE|DIFFICULT|BLOCKED),
                 status (PENDING|VERIFIED|REJECTED|SPAM),
                 observed_at, created_at, client_uuid (idempotency key)

User           : id, phone, fcm_token, created_at

SavedPlace     : user (FK→User), label (HOME|OFFICE|OTHER),
                 geom (POINT), hex (FK→HexCell), notify (bool)

AlertEvent     : id, hex/area, risk_level, window_start, window_end, message

AlertDelivery  : alert (FK→AlertEvent), user (FK→User),
                 sent_at, delivered_at (FCM receipt), status

BiasFactor     : station/region, multiplier, offset, valid_from, computed_at

CalibrationLog : actor, change_type, before, after, ts       # audit trail

ModerationLog  : actor, report (FK→FloodReport), action, ts  # audit trail
```

---

## §3.2 Risk Engine Definition (Authoritative)

```
hazard_class = bucket(rain_corrected_mm_per_h):
    LOW    < 7.5
    MODERATE ≥ 7.5  < 35
    HIGH     ≥ 35   < 64.5
    SEVERE   ≥ 64.5
    (IDF-tunable thresholds in admin)

rain_corrected = rain_raw * bias.multiplier + bias.offset

risk_level = RISK_MATRIX[hazard_class][susceptibility_bucket(fsi_score)]
    susceptibility_bucket:
        fsi < 0.33 → LOW
        fsi < 0.66 → MED
        else       → HIGH

confidence = f(model_agreement, station_density_nearby, forecast_lead_time)
```

---

## §3.3 Public API (Mobile) — Base `/api/v1`

| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/auth/otp/request` | `{phone}` | `{request_id}` |
| POST | `/auth/otp/verify` | `{request_id, code, fcm_token}` | `{access, refresh, user}` |
| GET | `/risk/hexes` | `?bbox=&ts=` | GeoJSON FeatureCollection (risk_level per hex) |
| GET | `/risk/location` | `?lat=&lng=` | `{risk_level, plain_text, hourly[24]{ts,risk_level}, explanation, confidence}` |
| GET | `/risk/overview` | — | `{forecast_rain_24h, max_rate_1h, confidence, summary{severe,high,moderate,low %}, hotspots[]}` |
| GET | `/radar/frames` | `?since=` | `[{ts, tile_url_template, intensity_legend}]` |
| POST | `/reports` | multipart: `{photo, lat, lng, depth, road, observed_at, client_uuid}` | FloodReport |
| GET | `/reports/nearby` | `?lat=&lng=&radius_m=1000&since_min=60` | `[FloodReport public fields]` |
| GET | `/places` | — | `[SavedPlace]` |
| POST | `/places` | `{label, lat, lng, notify}` | SavedPlace |
| PATCH | `/places/{id}` | `{notify}` | SavedPlace |
| GET | `/alerts` | `?scope=active\|history` | `[AlertEvent for user's places/location]` |
| POST | `/devices/token` | `{fcm_token}` | 204 |

---

## §3.4 Admin API — Base `/api/v1/admin` (JWT, role-gated)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/verify/stations/{id}/timeseries?window=72h` | Predicted vs observed series |
| GET | `/verify/errors?metric=mae\|bias\|corr` | Per-station metrics + trend |
| GET | `/verify/error-map?ts=` | Hex (predicted-observed) GeoJSON |
| GET | `/validate/reports-vs-risk?from=&to=` | Reports + active risk overlay |
| GET | `/validate/confusion?from=&to=` | Confusion matrix counts |
| GET | `/validate/hotspot-ranking` | Areas by agreement/disagreement |
| GET/PUT | `/calibrate/weights` | FSI weights + matrix thresholds (+preview) |
| POST | `/calibrate/backtest` | `{date}` → replayed risk vs known flooded localities |
| GET | `/health/feeds` | Last ingest ts per feed + stale flags |
| GET | `/health/stations` | Uptime map |
| GET | `/moderation/queue` | Pending reports |
| POST | `/moderation/{id}/action` | `{action}` → verify\|reject\|spam |
| GET | `/analytics/alerts` | Sent vs delivered by area/level |
| GET | `/export` | `?type=risk\|reports&from=&to=&fmt=csv\|geojson` |

---

## Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Backend | Django secret key |
| `DEBUG` | Backend | `True`/`False` |
| `ALLOWED_HOSTS` | Backend | Comma-separated |
| `DATABASE_URL` | Backend | PostgreSQL+PostGIS DSN |
| `REDIS_URL` | Backend | Redis connection URL |
| `FIREBASE_CREDENTIALS_JSON` | Backend | Firebase Admin SDK service account JSON path or inline |
| `AWS_ACCESS_KEY_ID` | Backend | S3/R2 access key |
| `AWS_SECRET_ACCESS_KEY` | Backend | S3/R2 secret key |
| `AWS_STORAGE_BUCKET_NAME` | Backend | S3/R2 bucket name |
| `AWS_S3_ENDPOINT_URL` | Backend | R2 or custom S3 endpoint |
| `ECMWF_API_KEY` | Backend | ECMWF forecast ingest key |
| `API_BASE_URL` | Mobile | Backend base URL (dart-define) |
| `GOOGLE_SERVICES_JSON` | Mobile | Firebase config |
| `VITE_API_BASE_URL` | Admin | Backend base URL |
| `VITE_MAPLIBRE_STYLE_URL` | Admin | MapLibre tile style URL |

---

## Contract Changes Log

| Phase | Date | Change | Author |
|-------|------|--------|--------|
| p0 | 2026-06-19 | Initial contract seeded from playbook §3 | Bootstrap |
