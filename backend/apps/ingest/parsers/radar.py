"""
IMD Doppler radar frame parser.

MOCK mode: fetches the latest frame from RainViewer's free public API
           (no API key required, global coverage including India).
           Falls back to a placeholder if RainViewer is unreachable.
REAL mode: fetches metadata from a configured radar tile API.

Anomaly rules (applied in both modes):
  - anomaly=True if dbz_max > 75 dBZ (hail-level; very rare over Hyderabad)
  - anomaly=True if dbz_min > 20 dBZ (baseline never that high)
  - georef_ok=False if the tile URL template is empty/missing
"""
import logging
from datetime import datetime

import numpy as np

logger = logging.getLogger("floodguard.ingest.radar")

DBZ_ANOMALY_MAX = 75.0
DBZ_ANOMALY_MIN = 20.0

# RainViewer public API — no auth required
_RAINVIEWER_API = "https://api.rainviewer.com/public/weather-maps.json"
_RAINVIEWER_TILE = "https://tilecache.rainviewer.com{path}/512/{{z}}/{{x}}/{{y}}/2/1_1.png"


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
        logger.warning("Radar anomaly: dbz_max=%.1f > %.1f", dbz_max, DBZ_ANOMALY_MAX)
        return True
    if dbz_min > DBZ_ANOMALY_MIN:
        logger.warning("Radar anomaly: dbz_min=%.1f suspiciously high", dbz_min)
        return True
    return False


def _mock_frame(ts: datetime) -> dict:
    """
    Fetch the most recent frame from RainViewer's free public radar API.
    Falls back to a synthetic placeholder if the network is unavailable.
    """
    import requests

    try:
        resp = requests.get(_RAINVIEWER_API, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        past_frames = data.get("radar", {}).get("past", [])
        if past_frames:
            latest = past_frames[-1]
            path = latest["path"]
            tile_url = _RAINVIEWER_TILE.format(path=path)
            seed = int(ts.timestamp()) % (2**31)
            rng = np.random.default_rng(seed=seed)
            return {
                "ts": ts,
                "tile_url_template": tile_url,
                "dbz_min": 0.0,
                "dbz_max": round(float(rng.uniform(10.0, 55.0)), 1),
            }
    except Exception as exc:
        logger.warning("RainViewer unavailable, using placeholder: %s", exc)

    # Fallback — tiles won't load but won't crash the ingest pipeline
    seed = int(ts.timestamp()) % (2**31)
    rng = np.random.default_rng(seed=seed)
    return {
        "ts": ts,
        "tile_url_template": (
            f"https://tilecache.rainviewer.com/v2/radar/nowcast"
            f"/{ts.strftime('%Y%m%d%H%M')}/512/{{z}}/{{x}}/{{y}}/2/1_1.png"
        ),
        "dbz_min": 0.0,
        "dbz_max": round(float(rng.uniform(10.0, 55.0)), 1),
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
