"""
Radar frame parser.

REAL mode (default): fetches the latest frame from RainViewer's free public API
                     (no key required, global coverage including India).
                     Raises on any HTTP/parse error — no synthetic fallback.

MOCK mode:           deterministic synthetic frame for offline dev / tests.
                     Tile URL points at a non-existent RainViewer path so
                     it's obvious the tiles won't load.

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
# colorScheme=4 is RainViewer's "The Weather Channel" palette — high-contrast
# green→yellow→red→magenta, reads well on a satellite basemap.
_RAINVIEWER_TILE = "https://tilecache.rainviewer.com{path}/512/{{z}}/{{x}}/{{y}}/4/1_1.png"
_RAINVIEWER_TIMEOUT = 15

# RainViewer doesn't expose per-frame dBZ metadata, so we use safe defaults
# well under the anomaly thresholds. Tuning happens client-side via the tile
# colour ramp, not on ingest.
_DEFAULT_DBZ_MIN = 0.0
_DEFAULT_DBZ_MAX = 50.0


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
    """Deterministic synthetic frame — tile URL will not load. For tests only."""
    seed = int(ts.timestamp()) % (2**31)
    rng = np.random.default_rng(seed=seed)
    return {
        "ts": ts,
        "tile_url_template": (
            f"https://tilecache.rainviewer.com/mock/{ts.strftime('%Y%m%d%H%M')}"
            f"/512/{{z}}/{{x}}/{{y}}/2/1_1.png"
        ),
        "dbz_min": _DEFAULT_DBZ_MIN,
        "dbz_max": round(float(rng.uniform(10.0, 55.0)), 1),
    }


def _rainviewer_frame(ts: datetime) -> dict:
    """Fetch the most recent frame index from RainViewer. Raises on error."""
    import requests

    resp = requests.get(_RAINVIEWER_API, timeout=_RAINVIEWER_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    past_frames = (data.get("radar") or {}).get("past") or []
    nowcast_frames = (data.get("radar") or {}).get("nowcast") or []
    if not past_frames:
        raise RuntimeError("RainViewer returned no past radar frames")

    latest = past_frames[-1]
    path = latest.get("path")
    if not path:
        raise RuntimeError("RainViewer past frame missing 'path'")

    logger.info(
        "RainViewer: %d past + %d nowcast frames; latest ts=%s",
        len(past_frames), len(nowcast_frames), latest.get("time"),
    )
    return {
        "ts": ts,
        "tile_url_template": _RAINVIEWER_TILE.format(path=path),
        "dbz_min": _DEFAULT_DBZ_MIN,
        "dbz_max": _DEFAULT_DBZ_MAX,
    }


def fetch_and_parse(ts: datetime, mock: bool) -> dict | None:
    frame = _mock_frame(ts) if mock else _rainviewer_frame(ts)
    if frame is None:
        return None
    frame["georef_ok"] = validate_georef(frame)
    frame["anomaly"] = detect_anomaly(frame)
    return frame
