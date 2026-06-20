"""
ECMWF precipitation parser.

MOCK mode (INGEST_MOCK=True):
    Generates synthetic monsoon-like rainfall for all hex centroids.
    Seeded from run_ts so the same hour always produces the same values (idempotent).

REAL mode:
    Downloads GRIB2 from ECMWF Open Data, parses with cfgrib/xarray,
    and samples total precipitation at each hex centroid.
"""
import logging
from datetime import datetime, timedelta

import numpy as np

logger = logging.getLogger("floodguard.ingest.ecmwf")


def _mock_forecast(run_ts: datetime, hex_cells: list) -> list[dict]:
    """Deterministic synthetic rainfall — same run_ts always returns same values."""
    seed = int(run_ts.timestamp()) % (2**31)
    rng = np.random.default_rng(seed=seed)

    # Simulate spatial rainfall field: one base rate + per-cell noise
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


def _real_forecast(run_ts: datetime, hex_cells: list, api_key: str) -> list[dict]:
    """
    Download ECMWF Open Data GRIB2 for the HYD bbox and sample at hex centroids.
    Requires: cfgrib, xarray, requests.
    """
    import tempfile

    import cfgrib  # noqa: F401 — verifies availability
    import requests
    import xarray as xr

    date_str = run_ts.strftime("%Y%m%d")
    hour_str = run_ts.strftime("%H")
    url = (
        f"https://data.ecmwf.int/forecasts/{date_str}/{hour_str}z/ifs/0p25/oper/"
        f"{date_str}{hour_str}0000-1h-oper-fc.grib2"
    )
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    logger.info("Fetching ECMWF GRIB from %s", url)
    resp = requests.get(url, headers=headers, timeout=120)
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as f:
        f.write(resp.content)
        grib_path = f.name

    ds = xr.open_dataset(grib_path, engine="cfgrib", filter_by_keys={"shortName": "tp"})
    tp = ds["tp"]  # total precipitation in metres

    records = []
    for cell in hex_cells:
        lat, lng = cell.centroid.y, cell.centroid.x
        try:
            val_m = float(tp.sel(latitude=lat, longitude=lng, method="nearest").values)
            val_mm = max(0.0, val_m * 1000)
        except Exception:
            val_mm = 0.0
        records.append({
            "hex_id": cell.h3_index,
            "valid_ts": run_ts + timedelta(hours=1),
            "run_ts": run_ts,
            "rain_1h": round(val_mm, 3),
            "rain_3h": round(val_mm * 2.5, 3),   # rough; real impl uses multi-step grib
            "rain_24h": round(val_mm * 18.0, 3),
            "source": "ECMWF",
        })
    return records


def fetch_and_parse(run_ts: datetime, hex_cells: list, mock: bool, api_key: str = "") -> list[dict]:
    if mock:
        logger.info("ECMWF mock: generating data for %d hexes at run_ts=%s", len(hex_cells), run_ts)
        return _mock_forecast(run_ts, hex_cells)
    return _real_forecast(run_ts, hex_cells, api_key)
