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

# One virtual AWS station per Assam district (centroid of the loaded district
# polygon). Real ground gauges aren't available for free, so precipitation is
# still sourced from Open-Meteo at these coords — but the station granularity
# now covers the whole state instead of just Hyderabad.
STATIONS = [
    {"station_id": "ASM_AWS_001", "name": "Bajali",                   "lat": 26.5042, "lng": 91.1453},
    {"station_id": "ASM_AWS_002", "name": "Baksa",                    "lat": 26.6650, "lng": 91.1966},
    {"station_id": "ASM_AWS_003", "name": "Barpeta",                  "lat": 26.2935, "lng": 90.9633},
    {"station_id": "ASM_AWS_004", "name": "Biswanath",                "lat": 26.8121, "lng": 93.3128},
    {"station_id": "ASM_AWS_005", "name": "Bongaigaon",               "lat": 26.3508, "lng": 90.6109},
    {"station_id": "ASM_AWS_006", "name": "Cachar",                   "lat": 24.8125, "lng": 92.8548},
    {"station_id": "ASM_AWS_007", "name": "Charaideo",                "lat": 27.0679, "lng": 95.0593},
    {"station_id": "ASM_AWS_008", "name": "Chirang",                  "lat": 26.6597, "lng": 90.5964},
    {"station_id": "ASM_AWS_009", "name": "Darrang",                  "lat": 26.4481, "lng": 92.0298},
    {"station_id": "ASM_AWS_010", "name": "Dhemaji",                  "lat": 27.5810, "lng": 94.7627},
    {"station_id": "ASM_AWS_011", "name": "Dhubri",                   "lat": 26.1199, "lng": 90.0271},
    {"station_id": "ASM_AWS_012", "name": "Dibrugarh",                "lat": 27.3679, "lng": 95.0524},
    {"station_id": "ASM_AWS_013", "name": "Dima Hasao",               "lat": 25.3779, "lng": 93.0309},
    {"station_id": "ASM_AWS_014", "name": "Goalpara",                 "lat": 26.0484, "lng": 90.6091},
    {"station_id": "ASM_AWS_015", "name": "Golaghat",                 "lat": 26.4420, "lng": 93.8311},
    {"station_id": "ASM_AWS_016", "name": "Hailakandi",               "lat": 24.4971, "lng": 92.5878},
    {"station_id": "ASM_AWS_017", "name": "Hojai",                    "lat": 25.9786, "lng": 92.9791},
    {"station_id": "ASM_AWS_018", "name": "Jorhat",                   "lat": 26.6956, "lng": 94.2767},
    {"station_id": "ASM_AWS_019", "name": "Kamrup",                   "lat": 26.1004, "lng": 91.4154},
    {"station_id": "ASM_AWS_020", "name": "Kamrup Metropolitan",      "lat": 26.1284, "lng": 91.8913},
    {"station_id": "ASM_AWS_021", "name": "Karbi Anglong",            "lat": 26.1569, "lng": 93.4048},
    {"station_id": "ASM_AWS_022", "name": "Kokrajhar",                "lat": 26.4932, "lng": 90.1193},
    {"station_id": "ASM_AWS_023", "name": "Lakhimpur",                "lat": 27.1705, "lng": 94.1300},
    {"station_id": "ASM_AWS_024", "name": "Majuli",                   "lat": 26.9369, "lng": 94.1698},
    {"station_id": "ASM_AWS_025", "name": "Morigaon",                 "lat": 26.2817, "lng": 92.2838},
    {"station_id": "ASM_AWS_026", "name": "Nagaon",                   "lat": 26.3630, "lng": 92.7536},
    {"station_id": "ASM_AWS_027", "name": "Nalbari",                  "lat": 26.3711, "lng": 91.3823},
    {"station_id": "ASM_AWS_028", "name": "Sivasagar",                "lat": 26.9703, "lng": 94.6648},
    {"station_id": "ASM_AWS_029", "name": "Sonitpur",                 "lat": 26.7603, "lng": 92.6518},
    {"station_id": "ASM_AWS_030", "name": "South Salmara-Mankachar",  "lat": 25.6967, "lng": 89.9191},
    {"station_id": "ASM_AWS_031", "name": "Sribhumi",                 "lat": 24.5795, "lng": 92.3790},
    {"station_id": "ASM_AWS_032", "name": "Tamulpur",                 "lat": 26.6520, "lng": 91.6231},
    {"station_id": "ASM_AWS_033", "name": "Tinsukia",                 "lat": 27.5810, "lng": 95.6176},
    {"station_id": "ASM_AWS_034", "name": "Udalguri",                 "lat": 26.7302, "lng": 92.0315},
    {"station_id": "ASM_AWS_035", "name": "West Karbi Anglong",       "lat": 25.8500, "lng": 92.5330},
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
