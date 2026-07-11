"""
AWS (Automatic Weather Station) rainfall parser.

MOCK mode:
    Deterministic synthetic observations for the 10 hardcoded Hyderabad GHMC
    stations. Seeded by ts. Only for offline dev / tests.

REAL mode (AWS_LIVE=True):
    Batched Open-Meteo Forecast API call with past_hours=24. Returns observed
    (past) hourly precipitation at each station lat/lng. Raises on any HTTP or
    parse error — no silent fallback to mock.

    Note: this is modeled precipitation (from the same source as the forecast),
    not a real ground-truth rain gauge. Until TGDPS/IMD expose a free real-time
    gauge API, this is the closest free proxy.
"""
import logging
from datetime import datetime, timezone as dt_tz

import numpy as np

logger = logging.getLogger("floodguard.ingest.aws")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEOUT = 30

# 10 GHMC AWS station locations (TGDPS network — kept as canonical station IDs
# even when precipitation is sourced from Open-Meteo).
STATIONS = [
    {"station_id": "HYD_AWS_001", "name": "Secunderabad",    "lat": 17.4435, "lng": 78.4987},
    {"station_id": "HYD_AWS_002", "name": "Hitech City",     "lat": 17.4450, "lng": 78.3762},
    {"station_id": "HYD_AWS_003", "name": "Kukatpally",      "lat": 17.4947, "lng": 78.3996},
    {"station_id": "HYD_AWS_004", "name": "LB Nagar",        "lat": 17.3464, "lng": 78.5519},
    {"station_id": "HYD_AWS_005", "name": "Mehdipatnam",     "lat": 17.3956, "lng": 78.4363},
    {"station_id": "HYD_AWS_006", "name": "Uppal",           "lat": 17.4046, "lng": 78.5593},
    {"station_id": "HYD_AWS_007", "name": "Begumpet",        "lat": 17.4449, "lng": 78.4679},
    {"station_id": "HYD_AWS_008", "name": "Vanasthalipuram", "lat": 17.3540, "lng": 78.5683},
    {"station_id": "HYD_AWS_009", "name": "Rajendranagar",   "lat": 17.3302, "lng": 78.4014},
    {"station_id": "HYD_AWS_010", "name": "Alwal",           "lat": 17.5043, "lng": 78.5000},
]
# Kept as alias for older imports.
MOCK_STATIONS = STATIONS


def _mock_observations(ts: datetime) -> list[dict]:
    """Deterministic synthetic observations seeded by timestamp."""
    seed = int(ts.timestamp()) % (2**31)
    rng = np.random.default_rng(seed=seed)

    results = []
    for station in STATIONS:
        r1h = round(float(rng.uniform(0.0, 40.0)), 2)
        results.append({
            **station,
            "ts": ts,
            "rain_1h": r1h,
            "rain_3h": round(r1h * float(rng.uniform(2.0, 3.5)), 2),
            "rain_24h": round(r1h * float(rng.uniform(10.0, 22.0)), 2),
        })
    return results


def _real_observations(ts: datetime) -> list[dict]:
    """Batched Open-Meteo call for all stations. Raises on error — no fallback."""
    import requests

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt_tz.utc)

    lats = [s["lat"] for s in STATIONS]
    lngs = [s["lng"] for s in STATIONS]

    params = {
        "latitude": ",".join(f"{v:.4f}" for v in lats),
        "longitude": ",".join(f"{v:.4f}" for v in lngs),
        "hourly": "precipitation",
        "past_hours": 24,
        "forecast_hours": 1,
        "timezone": "UTC",
    }
    logger.info("Open-Meteo AWS: batched call for %d stations", len(STATIONS))
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=OPEN_METEO_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    results = data if isinstance(data, list) else [data]

    if len(results) != len(STATIONS):
        raise RuntimeError(
            f"Open-Meteo returned {len(results)} station results for {len(STATIONS)} inputs"
        )

    observations: list[dict] = []
    for station, result in zip(STATIONS, results):
        hourly = result.get("hourly") or {}
        precip = hourly.get("precipitation") or []
        if not precip:
            raise RuntimeError(f"Open-Meteo AWS: no precipitation for {station['station_id']}")

        completed = [float(v) for v in precip[:-1] if v is not None]
        if not completed:
            raise RuntimeError(f"Open-Meteo AWS: empty past window for {station['station_id']}")

        r1h = round(completed[-1], 2)
        r3h = round(sum(completed[-3:]), 2)
        r24h = round(sum(completed[-24:]), 2)

        observations.append({
            **station,
            "ts": ts,
            "rain_1h": r1h,
            "rain_3h": r3h,
            "rain_24h": r24h,
        })

    logger.info("Open-Meteo AWS: parsed %d observations", len(observations))
    return observations


def fetch_and_parse(ts: datetime, mock: bool) -> list[dict]:
    if mock:
        logger.info("AWS mock: generating observations for %d stations at ts=%s", len(STATIONS), ts)
        return _mock_observations(ts)
    return _real_observations(ts)
