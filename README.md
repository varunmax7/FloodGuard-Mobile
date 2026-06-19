# FloodGuard 🛡️💧

> **Real-time urban flood alert system for Hyderabad**
> Flutter app · Django/PostGIS backend · React admin dashboard

## Repository Layout

```
floodguard/
├── CONTRACT.md              # API contracts, data models, env vars (single source of truth)
├── docker-compose.yml       # Local dev orchestration
├── .env.example             # Copy to .env and fill in secrets
├── backend/                 # Django 5 + DRF + Celery + PostGIS
├── mobile/                  # Flutter 3.24 app (iOS + Android)
├── admin/                   # React 18 + Vite + TailwindCSS admin dashboard
└── infra/                   # CI/CD + deploy configs
```

## Quickstart

### Prerequisites
- Docker Desktop ≥ 4.25
- Flutter 3.24+ (`flutter doctor` clean)
- Node.js 20 LTS
- Android Studio / Xcode for mobile emulator

### 1 · Start backend services

```bash
cp .env.example .env   # Fill in secrets
docker compose up -d   # db, redis, web, worker, beat
docker compose logs -f web
```

### 2 · Run Flutter app

```bash
cd mobile
flutter pub get
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

### 3 · Run admin dashboard

```bash
cd admin
npm install
npm run dev
# Open http://localhost:5173
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | Flutter 3.24, Riverpod 2, MapLibre GL, go_router, Drift |
| Backend | Django 5, DRF, GeoDjango, PostGIS 3.4, Celery 5, Redis |
| Spatial | H3 (res-9), rasterio, xarray, shapely |
| Auth | Firebase Auth (phone OTP) + SimpleJWT |
| Push | Firebase Cloud Messaging |
| Admin | React 18, Vite, TailwindCSS, shadcn/ui, MapLibre GL JS |
| Infra | Docker Compose, Railway, Cloudflare R2, GitHub Actions |

## Development Phases

| Tag | Phase | Status |
|-----|-------|--------|
| p0 | Monorepo Scaffold & Infra | ✅ |
| p1 | Geospatial Data Layer (PostGIS + H3) | ⬜ |
| p2 | Ingest Pipeline (ECMWF + Radar) | ⬜ |
| p3 | Risk Engine | ⬜ |
| p4 | REST API Layer | ⬜ |
| p5 | Flutter Auth + Navigation Shell | ⬜ |
| p6 | Home + Risk Map screens | ⬜ |
| p7 | Alerts + Report flow | ⬜ |
| p8 | Live Radar screen | ⬜ |
| p9 | Offline sync + background | ⬜ |
| p10 | Admin: Monitoring dashboard | ⬜ |
| p11 | Admin: Calibration + moderation | ⬜ |
| p12 | Admin: Analytics + export | ⬜ |
| p13 | Production deploy (Railway + R2) | ⬜ |

## Contract

All API shapes, data models, and environment variables are documented in [CONTRACT.md](./CONTRACT.md). **Read this before writing any code.**

## License

Proprietary — FloodGuard Solutions Pvt. Ltd.
