"""
AWS (Automatic Weather Station) rainfall parser.

MOCK mode:
    Deterministic synthetic observations for the 59 Telangana + Andhra Pradesh
    district stations. Seeded by ts. Only for offline dev / tests.

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

# One virtual AWS station per Telangana / Andhra Pradesh district (approximate
# centroid). Real ground gauges aren't available for free, so precipitation is
# still sourced from Open-Meteo at these coords — station granularity covers
# the union of the two states.
STATIONS = [
    # ── Telangana (33) ──────────────────────────────────────────────────────
    {"station_id": "TG_AWS_001", "name": "Adilabad",                  "lat": 19.6641, "lng": 78.5320},
    {"station_id": "TG_AWS_002", "name": "Bhadradri Kothagudem",      "lat": 17.5480, "lng": 80.6180},
    {"station_id": "TG_AWS_003", "name": "Hanumakonda",               "lat": 17.9985, "lng": 79.5910},
    {"station_id": "TG_AWS_004", "name": "Hyderabad",                 "lat": 17.3850, "lng": 78.4867},
    {"station_id": "TG_AWS_005", "name": "Jagtial",                   "lat": 18.7910, "lng": 78.9110},
    {"station_id": "TG_AWS_006", "name": "Jangaon",                   "lat": 17.7220, "lng": 79.1560},
    {"station_id": "TG_AWS_007", "name": "Jayashankar Bhupalpally",   "lat": 18.4200, "lng": 79.9500},
    {"station_id": "TG_AWS_008", "name": "Jogulamba Gadwal",          "lat": 16.2350, "lng": 77.7940},
    {"station_id": "TG_AWS_009", "name": "Kamareddy",                 "lat": 18.3220, "lng": 78.3410},
    {"station_id": "TG_AWS_010", "name": "Karimnagar",                "lat": 18.4386, "lng": 79.1288},
    {"station_id": "TG_AWS_011", "name": "Khammam",                   "lat": 17.2473, "lng": 80.1514},
    {"station_id": "TG_AWS_012", "name": "Komaram Bheem Asifabad",    "lat": 19.3600, "lng": 79.2830},
    {"station_id": "TG_AWS_013", "name": "Mahabubabad",               "lat": 17.5990, "lng": 80.0030},
    {"station_id": "TG_AWS_014", "name": "Mahabubnagar",              "lat": 16.7488, "lng": 77.9857},
    {"station_id": "TG_AWS_015", "name": "Mancherial",                "lat": 18.8710, "lng": 79.4460},
    {"station_id": "TG_AWS_016", "name": "Medak",                     "lat": 18.0500, "lng": 78.2680},
    {"station_id": "TG_AWS_017", "name": "Medchal-Malkajgiri",        "lat": 17.5510, "lng": 78.5480},
    {"station_id": "TG_AWS_018", "name": "Mulugu",                    "lat": 18.1930, "lng": 80.0140},
    {"station_id": "TG_AWS_019", "name": "Nagarkurnool",              "lat": 16.4830, "lng": 78.3260},
    {"station_id": "TG_AWS_020", "name": "Nalgonda",                  "lat": 17.0575, "lng": 79.2670},
    {"station_id": "TG_AWS_021", "name": "Narayanpet",                "lat": 16.7460, "lng": 77.4970},
    {"station_id": "TG_AWS_022", "name": "Nirmal",                    "lat": 19.0980, "lng": 78.3450},
    {"station_id": "TG_AWS_023", "name": "Nizamabad",                 "lat": 18.6725, "lng": 78.0941},
    {"station_id": "TG_AWS_024", "name": "Peddapalli",                "lat": 18.6150, "lng": 79.3740},
    {"station_id": "TG_AWS_025", "name": "Rajanna Sircilla",          "lat": 18.3860, "lng": 78.8100},
    {"station_id": "TG_AWS_026", "name": "Ranga Reddy",               "lat": 17.2000, "lng": 78.1000},
    {"station_id": "TG_AWS_027", "name": "Sangareddy",                "lat": 17.6250, "lng": 78.0810},
    {"station_id": "TG_AWS_028", "name": "Siddipet",                  "lat": 18.1010, "lng": 78.8480},
    {"station_id": "TG_AWS_029", "name": "Suryapet",                  "lat": 17.1400, "lng": 79.6210},
    {"station_id": "TG_AWS_030", "name": "Vikarabad",                 "lat": 17.3370, "lng": 77.9040},
    {"station_id": "TG_AWS_031", "name": "Wanaparthy",                "lat": 16.3620, "lng": 78.0630},
    {"station_id": "TG_AWS_032", "name": "Warangal",                  "lat": 17.9750, "lng": 79.6120},
    {"station_id": "TG_AWS_033", "name": "Yadadri Bhuvanagiri",       "lat": 17.5400, "lng": 78.8830},
    # ── Andhra Pradesh (26) ─────────────────────────────────────────────────
    {"station_id": "AP_AWS_001", "name": "Alluri Sitharama Raju",     "lat": 17.8760, "lng": 82.4630},
    {"station_id": "AP_AWS_002", "name": "Anakapalli",                "lat": 17.6910, "lng": 83.0030},
    {"station_id": "AP_AWS_003", "name": "Anantapur",                 "lat": 14.6819, "lng": 77.6006},
    {"station_id": "AP_AWS_004", "name": "Annamayya",                 "lat": 14.0250, "lng": 78.9110},
    {"station_id": "AP_AWS_005", "name": "Bapatla",                   "lat": 15.9040, "lng": 80.4670},
    {"station_id": "AP_AWS_006", "name": "Chittoor",                  "lat": 13.2172, "lng": 79.1003},
    {"station_id": "AP_AWS_007", "name": "East Godavari",             "lat": 17.0000, "lng": 81.7800},
    {"station_id": "AP_AWS_008", "name": "Eluru",                     "lat": 16.7108, "lng": 81.0952},
    {"station_id": "AP_AWS_009", "name": "Guntur",                    "lat": 16.3067, "lng": 80.4365},
    {"station_id": "AP_AWS_010", "name": "Kakinada",                  "lat": 16.9891, "lng": 82.2475},
    {"station_id": "AP_AWS_011", "name": "Konaseema",                 "lat": 16.5730, "lng": 82.0000},
    {"station_id": "AP_AWS_012", "name": "Krishna",                   "lat": 16.3000, "lng": 81.0000},
    {"station_id": "AP_AWS_013", "name": "Kurnool",                   "lat": 15.8281, "lng": 78.0373},
    {"station_id": "AP_AWS_014", "name": "Nandyal",                   "lat": 15.4780, "lng": 78.4830},
    {"station_id": "AP_AWS_015", "name": "NTR",                       "lat": 16.5062, "lng": 80.6480},
    {"station_id": "AP_AWS_016", "name": "Palnadu",                   "lat": 16.3520, "lng": 79.9500},
    {"station_id": "AP_AWS_017", "name": "Parvathipuram Manyam",      "lat": 18.7770, "lng": 83.4260},
    {"station_id": "AP_AWS_018", "name": "Prakasam",                  "lat": 15.5040, "lng": 79.4890},
    {"station_id": "AP_AWS_019", "name": "Sri Potti Sriramulu Nellore","lat": 14.4426, "lng": 79.9865},
    {"station_id": "AP_AWS_020", "name": "Sri Sathya Sai",            "lat": 14.1670, "lng": 77.8000},
    {"station_id": "AP_AWS_021", "name": "Srikakulam",                "lat": 18.2949, "lng": 83.8938},
    {"station_id": "AP_AWS_022", "name": "Tirupati",                  "lat": 13.6288, "lng": 79.4192},
    {"station_id": "AP_AWS_023", "name": "Visakhapatnam",             "lat": 17.6868, "lng": 83.2185},
    {"station_id": "AP_AWS_024", "name": "Vizianagaram",              "lat": 18.1067, "lng": 83.3956},
    {"station_id": "AP_AWS_025", "name": "West Godavari",             "lat": 16.7500, "lng": 81.3000},
    {"station_id": "AP_AWS_026", "name": "YSR Kadapa",                "lat": 14.4673, "lng": 78.8242},
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
