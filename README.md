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
- Flutter 3.24+ (`flutter doctor` clean)
- Node.js 20 LTS
- Android Studio / Xcode for mobile emulator
- PostgreSQL 16 + PostGIS (local dev) **or** Docker Desktop (team/production)

### 1 · Start backend services (local PostgreSQL — no Docker needed for dev)

```bash
# Install PostgreSQL + PostGIS once
brew install postgresql@16 postgis
brew services start postgresql@16

# Create DB
psql postgres -c "CREATE USER floodguard WITH PASSWORD 'floodguard';"
psql postgres -c "CREATE DATABASE floodguard OWNER floodguard;"
psql floodguard -c "CREATE EXTENSION postgis;"

# Install Python deps
cd backend
pip install -r requirements.txt

# Run migrations + start server
python manage.py migrate
python manage.py createsuperuser   # phone number + password
python manage.py runserver
# Admin → http://localhost:8000/admin
```

---

> ### 🐳 Docker — When You Need It
>
> Docker is **not required** during local development (Phases 0–12).
> Install and use Docker when you reach these milestones:
>
> | Milestone | Why Docker is needed |
> |-----------|----------------------|
> | **Phase 13 — Production deploy** | Railway deployment uses the Docker image |
> | **Running Celery worker + beat locally** | Need Redis + worker + beat all running together |
> | **Onboarding a new team member** | `docker compose up` gives everyone the same environment instantly |
> | **CI/CD pipeline** | GitHub Actions builds and pushes the Docker image on tag |
>
> When you're ready: `brew install --cask docker`, open Docker Desktop, then:
> ```bash
> cp .env.example .env
> docker compose up -d   # db, redis, web, worker, beat
> ```

---

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
| p1 | Geospatial Data Layer (PostGIS + H3) | ✅ |
| p2 | Auth (Phone OTP) & Saved Places API | ✅ |
| p3 | Data Ingestion Pipeline (ECMWF + AWS + Radar + Bias) | ✅ |
| p4 | Risk Engine & Public Risk/Radar APIs | ✅ |
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
