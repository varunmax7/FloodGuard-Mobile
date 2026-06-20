"""FloodGuard Celery application + beat schedule."""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "floodguard.settings")

app = Celery("floodguard")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ── Beat schedule ─────────────────────────────────────────────────────────────
# These are the default schedules. When using DatabaseScheduler (production)
# run `manage.py setup_beat_schedules` to seed them into the DB so they
# can be modified via the Django admin Periodic Tasks UI.
app.conf.beat_schedule = {
    "ingest-ecmwf-hourly": {
        "task": "apps.ingest.tasks.ingest_ecmwf",
        "schedule": crontab(minute=0),           # top of every hour
    },
    "ingest-aws-15min": {
        "task": "apps.ingest.tasks.ingest_aws",
        "schedule": crontab(minute="0,15,30,45"),
    },
    "ingest-radar-10min": {
        "task": "apps.ingest.tasks.ingest_radar",
        "schedule": crontab(minute="*/10"),
    },
    "recompute-bias-hourly": {
        "task": "apps.ingest.tasks.recompute_bias",
        "schedule": crontab(minute=5),           # 5 past every hour (after ECMWF lands)
    },
    "recompute-risk-hourly": {
        "task": "apps.risk.tasks.recompute_all_risk",
        "schedule": crontab(minute=15),          # 15 past every hour (after ECMWF + bias)
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
