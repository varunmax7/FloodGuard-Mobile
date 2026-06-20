# FloodGuard Operations Runbook

> **Audience:** On-call engineers and ops team.  
> **Stack:** Django (Railway `web`), Celery (`worker` + `beat`), PostgreSQL/PostGIS, Redis, Cloudflare R2.

---

## 1. Service Map

| Service | Railway name | Health check |
|---|---|---|
| Django API | `web` | `GET /api/v1/readyz/` → 200 |
| Celery worker | `worker` | `celery inspect ping` |
| Celery beat | `beat` | process running |
| PostgreSQL | Railway managed | Railway dashboard |
| Redis | Railway managed | Railway dashboard |

---

## 2. Restart Services

### Restart all (Railway CLI)
```bash
railway up --service web
railway up --service worker
railway up --service beat
```

### Force redeploy via GitHub tag
Push a new semver tag — CI builds and deploys automatically:
```bash
git tag v1.0.1 && git push origin v1.0.1
```

### Emergency restart (Railway dashboard)
Dashboard → Project → Service → **Restart**.

---

## 3. Replay Ingest (Storm Recovery)

If data feeds were unavailable and you need to backfill:

```bash
# SSH into the web container (Railway shell)
railway run --service web -- python manage.py shell
```

Inside the shell:
```python
from apps.ingest.tasks import ingest_ecmwf, ingest_aws_observations, ingest_radar
from apps.risk.tasks import recompute_all_risk

ingest_ecmwf.apply()
ingest_aws_observations.apply()
ingest_radar.apply()
recompute_all_risk.apply()
```

Or trigger via Celery:
```bash
railway run --service worker -- celery -A floodguard call apps.risk.tasks.recompute_all_risk
```

---

## 4. Run Migrations

Migrations run automatically during `release` on Railway. To run manually:
```bash
railway run --service web -- python manage.py migrate --noinput
```

Check pending migrations:
```bash
railway run --service web -- python manage.py showmigrations
```

---

## 5. Rotate Keys & Secrets

### JWT Secret
1. Generate: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
2. Set `SECRET_KEY` in Railway environment variables for `web`, `worker`, `beat`.
3. Restart all three services.
4. All existing JWTs are invalidated — users will need to re-login.

### Firebase Service Account
1. Create a new key in Firebase console → Project Settings → Service Accounts.
2. Set `FIREBASE_CREDENTIALS_JSON` (base64-encoded JSON) in Railway env.
3. Restart `web` and `worker`.
4. Revoke the old key in Firebase console.

### Cloudflare R2 Keys
1. Generate new API token in Cloudflare dashboard.
2. Update `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in Railway env.
3. Restart `web` and `worker`.

### Sentry DSN
Update `SENTRY_DSN` in Railway env; restart services.

---

## 6. Incident Steps

### Scenario: Risk feed stale (no new RiskSnapshots)

1. Check admin dashboard **§2.4 System Health → Feed Status** — look for red stale flags.
2. Check Celery worker logs: Railway → `worker` → Logs.
3. Verify ECMWF API key is valid: `ECMWF_API_KEY` env var.
4. Trigger manual ingest (see §3).
5. If ECMWF is down: set `INGEST_MOCK=True` temporarily to serve last-known risk.

### Scenario: API returning 5xx

1. Check `GET /api/v1/readyz/` — identifies DB vs cache issues.
2. Check Railway `web` logs for stack traces (also in Sentry).
3. If DB is down: Railway dashboard → PostgreSQL → Status.
4. If OOM: scale up RAM or reduce Gunicorn workers in `railway.toml`.

### Scenario: Push notifications not delivered

1. Check admin dashboard **§2.6 Analytics → Alerts sent vs delivered**.
2. Check `AlertDelivery` rows with `status=FAILED`.
3. Verify `FIREBASE_CREDENTIALS_JSON` is valid — test with:
   ```bash
   railway run --service web -- python manage.py shell -c "from floodguard.firebase import send_fcm_notification; print(send_fcm_notification('test-token', 'test', 'test'))"
   ```
4. Check Firebase console for delivery errors.

### Scenario: Photo uploads failing

1. Check `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL` in Railway env.
2. Verify R2 bucket exists and the key has write permission.
3. Check Sentry for `ClientError` from boto3.

### Scenario: Flood reports not appearing on map after moderation

1. Confirm report `status=VERIFIED` in Django admin.
2. Check `GET /api/v1/reports/nearby/?lat=...&lng=...` — verify filters.
3. Clear cache: `railway run --service web -- python manage.py shell -c "from django.core.cache import cache; cache.clear()"`

---

## 7. Useful Management Commands

| Command | Purpose |
|---|---|
| `python manage.py build_hexgrid` | Regenerate H3 hex grid |
| `python manage.py load_fsi --layers <dir>` | Reload FSI rasters into hexes |
| `python manage.py seed_p11` | Seed forecast-verification fixture data |
| `python manage.py seed_p12` | Seed moderation/analytics fixture data |
| `python manage.py createsuperuser` | Create admin user |
| `python manage.py collectstatic --noinput` | Re-collect static files |

---

## 8. Environment Variable Reference

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Django secret key (64+ chars) |
| `DEBUG` | — | `False` in production |
| `DATABASE_URL` | ✅ | PostGIS connection string |
| `REDIS_URL` | ✅ | Redis broker URL |
| `CACHE_URL` | — | Redis cache URL (defaults to LocMem if unset) |
| `ALLOWED_HOSTS` | ✅ | Comma-separated allowed hostnames |
| `CORS_ALLOWED_ORIGINS` | ✅ | Comma-separated admin dashboard origin |
| `FIREBASE_CREDENTIALS_JSON` | ✅ | Base64-encoded service account JSON |
| `AWS_ACCESS_KEY_ID` | ✅ | R2/S3 access key |
| `AWS_SECRET_ACCESS_KEY` | ✅ | R2/S3 secret key |
| `AWS_STORAGE_BUCKET_NAME` | ✅ | R2/S3 bucket name |
| `AWS_S3_ENDPOINT_URL` | ✅ | R2 endpoint (e.g., `https://<acct>.r2.cloudflarestorage.com`) |
| `ECMWF_API_KEY` | — | ECMWF API key (INGEST_MOCK=True bypasses) |
| `TGDPS_API_URL` | — | TGDPS AWS rain gauge API URL |
| `TGDPS_API_KEY` | — | TGDPS API key |
| `RADAR_API_URL` | — | Radar tile API URL |
| `RADAR_API_KEY` | — | Radar API key |
| `INGEST_MOCK` | — | `True` = use fixture data (no live API calls) |
| `SENTRY_DSN` | — | Sentry DSN for error tracking |
