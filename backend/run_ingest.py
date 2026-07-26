"""End-to-end refresh cycle: ingest live feeds → recompute risk → clear cache.

Runs the full pipeline in one shot so the launchd/cron/beat wrapper only has
to invoke this one script. Exits non-zero if any step fails so schedulers can
surface the failure.
"""
import os
import sys
import time

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "floodguard.settings")
django.setup()

from django.core.cache import cache  # noqa: E402

from apps.ingest.tasks import (  # noqa: E402
    ingest_aws,
    ingest_ecmwf,
    ingest_radar,
    recompute_bias,
)
from apps.risk.tasks import recompute_all_risk  # noqa: E402


def _run(label: str, fn):
    t0 = time.perf_counter()
    result = fn.apply().get()
    dt = time.perf_counter() - t0
    print(f"  → {label:10s} {result} ({dt:.2f}s)")
    return result


def main() -> int:
    try:
        print("Refresh cycle:")
        _run("ECMWF",   ingest_ecmwf)
        _run("AWS",     ingest_aws)
        _run("Radar",   ingest_radar)
        _run("Bias",    recompute_bias)
        _run("Risk",    recompute_all_risk)

        # The /risk/* views cache responses for 60s. Punch that cache so the
        # freshly-computed snapshots surface immediately instead of after the
        # next natural expiry.
        cache.clear()
        print("  → cache     cleared")
        print("Refresh cycle complete.")
        return 0
    except Exception as exc:  # noqa: BLE001 — top-level guard for scheduler
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
