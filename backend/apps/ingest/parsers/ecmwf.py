"""
Forecast precipitation parser.

MOCK mode (INGEST_MOCK=True):
    Generates synthetic monsoon-like rainfall for all hex centroids.
    Seeded from run_ts so the same hour always produces the same values (idempotent).
    Only used in local dev / unit tests.

REAL mode (INGEST_MOCK=False):
    Calls the free Open-Meteo Forecast API (no API key, ECMWF/GFS blended).
    Samples hourly precipitation at each hex centroid.
    Fails hard on network/parse errors — no silent fallback to mock.
"""
import logging
from datetime import datetime, timedelta, timezone as dt_tz

import numpy as np

logger = logging.getLogger("floodguard.ingest.ecmwf")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEOUT = 60         # seconds
FORECAST_SOURCE = "OPEN_METEO"

# Open-Meteo's underlying ECMWF/GFS grid is ~10 km; sampling per hex (100 m) is
# massive oversampling and overwhelms the API rate limit. Instead sample a
# coarse grid across the bbox in ONE call, then nearest-assign to hexes.
SAMPLE_GRID_NX = 8   # ~6 km resolution across a 49 km bbox
SAMPLE_GRID_NY = 5   # ~6 km resolution across a 32 km bbox


def _mock_forecast(run_ts: datetime, hex_cells: list) -> list[dict]:
    """Deterministic synthetic rainfall — same run_ts always returns same values."""
    seed = int(run_ts.timestamp()) % (2**31)
    rng = np.random.default_rng(seed=seed)

    base_1h = float(rng.uniform(0.5, 45.0))
    noise = rng.uniform(0.5, 1.5, size=len(hex_cells))

    records = []
    for i, cell in enumerate(hex_cells):
        r1h = round(float(base_1h * noise[i]), 3)
        records.append({
            "hex_id": cell.h3_index,
            "valid_ts": run_ts + timedelta(hours=1),
            "run_ts": run_ts,
            "rain_1h": r1h,
            "rain_3h": round(r1h * float(rng.uniform(2.0, 3.5)), 3),
            "rain_24h": round(r1h * float(rng.uniform(10.0, 22.0)), 3),
            "source": "ECMWF",
        })
    return records


def _open_meteo_batch(lats: list[float], lngs: list[float]) -> list[dict]:
    """Call Open-Meteo for a batch of coordinates. Returns list of per-location dicts."""
    import requests

    params = {
        "latitude": ",".join(f"{v:.4f}" for v in lats),
        "longitude": ",".join(f"{v:.4f}" for v in lngs),
        "hourly": "precipitation",
        "forecast_days": 2,
        "timezone": "UTC",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=OPEN_METEO_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    # Single-location responses come as an object; batched as a list.
    if isinstance(data, dict):
        return [data]
    return data


def _sum_from(times: list[str], values: list[float], run_ts: datetime, hours: int) -> float:
    """
    Sum `values` over the `hours` hours immediately following run_ts.
    Open-Meteo hourly precipitation[i] is accumulated rainfall in the hour ending at time[i].
    """
    total = 0.0
    ts_iso = run_ts.astimezone(dt_tz.utc).strftime("%Y-%m-%dT%H:%M")
    start_idx = None
    for i, t in enumerate(times):
        if t >= ts_iso:
            start_idx = i
            break
    if start_idx is None:
        return 0.0
    for i in range(start_idx, min(start_idx + hours, len(values))):
        v = values[i]
        if v is not None:
            total += float(v)
    return total


def _real_forecast(run_ts: datetime, hex_cells: list) -> list[dict]:
    """
    Sample Open-Meteo at a coarse grid over the hex bbox (one API call),
    then nearest-assign each hex to a grid point. Raises on any HTTP/parse
    error — no fallback to mock.
    """
    if not hex_cells:
        return []

    if run_ts.tzinfo is None:
        run_ts = run_ts.replace(tzinfo=dt_tz.utc)
    run_ts = run_ts.astimezone(dt_tz.utc).replace(minute=0, second=0, microsecond=0)

    # Build the sample grid across the hex bbox
    lats_h = [c.centroid.y for c in hex_cells]
    lngs_h = [c.centroid.x for c in hex_cells]
    min_lat, max_lat = min(lats_h), max(lats_h)
    min_lng, max_lng = min(lngs_h), max(lngs_h)

    # Nudge to avoid zero-span bbox
    if max_lat - min_lat < 1e-6:
        max_lat = min_lat + 1e-3
    if max_lng - min_lng < 1e-6:
        max_lng = min_lng + 1e-3

    sample_lats = np.linspace(min_lat, max_lat, SAMPLE_GRID_NY).tolist()
    sample_lngs = np.linspace(min_lng, max_lng, SAMPLE_GRID_NX).tolist()

    # Flatten to a single list of (lat, lng) — order is iy * NX + ix
    grid_lats, grid_lngs = [], []
    for lat in sample_lats:
        for lng in sample_lngs:
            grid_lats.append(lat)
            grid_lngs.append(lng)

    logger.info(
        "Open-Meteo: sampling %dx%d=%d grid points over bbox %.3f,%.3f→%.3f,%.3f",
        SAMPLE_GRID_NX, SAMPLE_GRID_NY, len(grid_lats),
        min_lng, min_lat, max_lng, max_lat,
    )
    results = _open_meteo_batch(grid_lats, grid_lngs)

    if len(results) != len(grid_lats):
        raise RuntimeError(
            f"Open-Meteo returned {len(results)} results for {len(grid_lats)} grid points"
        )

    # Pre-compute per-sample rain totals
    sample_rain: list[tuple[float, float, float]] = []
    for i, result in enumerate(results):
        hourly = result.get("hourly") or {}
        times = hourly.get("time") or []
        precip = hourly.get("precipitation") or []
        if not times or not precip:
            raise RuntimeError(f"Open-Meteo: missing hourly data at sample {i}")
        r1h = _sum_from(times, precip, run_ts, 1)
        r3h = _sum_from(times, precip, run_ts, 3)
        r24h = _sum_from(times, precip, run_ts, 24)
        sample_rain.append((r1h, r3h, r24h))

    # Nearest-neighbour assign each hex to a grid point (O(1) index math)
    lng_span = max_lng - min_lng
    lat_span = max_lat - min_lat
    records: list[dict] = []
    for cell in hex_cells:
        lat, lng = cell.centroid.y, cell.centroid.x
        ix = min(SAMPLE_GRID_NX - 1, max(0, int((lng - min_lng) / lng_span * SAMPLE_GRID_NX)))
        iy = min(SAMPLE_GRID_NY - 1, max(0, int((lat - min_lat) / lat_span * SAMPLE_GRID_NY)))
        r1h, r3h, r24h = sample_rain[iy * SAMPLE_GRID_NX + ix]
        records.append({
            "hex_id": cell.h3_index,
            "valid_ts": run_ts + timedelta(hours=1),
            "run_ts": run_ts,
            "rain_1h": round(r1h, 3),
            "rain_3h": round(r3h, 3),
            "rain_24h": round(r24h, 3),
            "source": FORECAST_SOURCE,
        })

    logger.info("Open-Meteo: assigned forecasts to %d hexes for run_ts=%s", len(records), run_ts)
    return records


def fetch_and_parse(run_ts: datetime, hex_cells: list, mock: bool) -> list[dict]:
    if mock:
        logger.info("Forecast mock: generating data for %d hexes at run_ts=%s", len(hex_cells), run_ts)
        return _mock_forecast(run_ts, hex_cells)
    return _real_forecast(run_ts, hex_cells)
