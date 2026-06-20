"""
TGDPS AWS (Automatic Weather Station) rainfall parser.

MOCK mode: returns observations for 10 hardcoded Hyderabad GHMC stations.
REAL mode: calls the TGDPS REST API.
"""
import logging
from datetime import datetime

import numpy as np

logger = logging.getLogger("floodguard.ingest.aws")

# 10 real GHMC AWS station locations (TGDPS network)
MOCK_STATIONS = [
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


def _mock_observations(ts: datetime) -> list[dict]:
    """Deterministic synthetic observations seeded by timestamp."""
    seed = int(ts.timestamp()) % (2**31)
    rng = np.random.default_rng(seed=seed)

    results = []
    for station in MOCK_STATIONS:
        r1h = round(float(rng.uniform(0.0, 40.0)), 2)
        results.append({
            **station,
            "ts": ts,
            "rain_1h": r1h,
            "rain_3h": round(r1h * float(rng.uniform(2.0, 3.5)), 2),
            "rain_24h": round(r1h * float(rng.uniform(10.0, 22.0)), 2),
        })
    return results


def _real_observations(ts: datetime, api_url: str, api_key: str) -> list[dict]:
    import requests

    resp = requests.get(
        f"{api_url}/observations",
        params={"ts": ts.isoformat(), "format": "json"},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_and_parse(ts: datetime, mock: bool, api_url: str = "", api_key: str = "") -> list[dict]:
    if mock:
        logger.info("AWS mock: generating observations for %d stations at ts=%s", len(MOCK_STATIONS), ts)
        return _mock_observations(ts)
    return _real_observations(ts, api_url, api_key)
