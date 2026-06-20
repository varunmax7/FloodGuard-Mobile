"""
IMD Doppler radar frame parser.

MOCK mode: generates a synthetic radar frame for Hyderabad.
REAL mode: fetches metadata from a radar tile API.

Anomaly rules (applied in both modes):
  - anomaly=True if dbz_max > 75 dBZ (hail-level; very rare over Hyderabad)
  - anomaly=True if dbz_min > 20 dBZ (baseline never that high)
  - georef_ok=False if the tile URL template is empty/missing
"""
import logging
from datetime import datetime

import numpy as np

logger = logging.getLogger("floodguard.ingest.radar")

DBZ_ANOMALY_MAX = 75.0   # dBZ threshold above which we flag
DBZ_ANOMALY_MIN = 20.0   # baseline dBZ should be near 0


def validate_georef(frame: dict) -> bool:
    url = frame.get("tile_url_template", "")
    if not url or "{z}" not in url:
        logger.warning("Radar georef failed: invalid tile_url_template")
        return False
    return True


def detect_anomaly(frame: dict) -> bool:
    dbz_max = frame.get("dbz_max", 0.0)
    dbz_min = frame.get("dbz_min", 0.0)
    if dbz_max > DBZ_ANOMALY_MAX:
        logger.warning("Radar anomaly: dbz_max=%.1f > threshold %.1f", dbz_max, DBZ_ANOMALY_MAX)
        return True
    if dbz_min > DBZ_ANOMALY_MIN:
        logger.warning("Radar anomaly: dbz_min=%.1f suspiciously high", dbz_min)
        return True
    return False


def _mock_frame(ts: datetime) -> dict:
    seed = int(ts.timestamp()) % (2**31)
    rng = np.random.default_rng(seed=seed)
    dbz_max = round(float(rng.uniform(10.0, 65.0)), 1)
    return {
        "ts": ts,
        "tile_url_template": (
            f"https://mock-radar.example.com"
            f"/{ts.strftime('%Y%m%d%H%M')}/{{z}}/{{x}}/{{y}}.png"
        ),
        "dbz_min": 0.0,
        "dbz_max": dbz_max,
    }


def _real_frame(ts: datetime, api_url: str, api_key: str) -> dict | None:
    import requests

    resp = requests.get(
        f"{api_url}/radar/latest",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def fetch_and_parse(ts: datetime, mock: bool, api_url: str = "", api_key: str = "") -> dict | None:
    frame = _mock_frame(ts) if mock else _real_frame(ts, api_url, api_key)
    if frame is None:
        return None

    frame["georef_ok"] = validate_georef(frame)
    frame["anomaly"] = detect_anomaly(frame)
    return frame
