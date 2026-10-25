"""Load districts (DS-6/DS-9) and places (DS-8) — see data/README.md.

Run once (idempotent, upserts on conflict):
    docker compose exec api python -m scripts.seed_reference_data
"""
import asyncio
import json
from pathlib import Path

from sqlalchemy import text

from app.db import engine

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


async def seed_districts() -> int:
    districts = json.load(open(DATA_DIR / "districts_ap_od.geojson"))["features"]
    name_te = json.load(open(DATA_DIR / "district_name_te.json"))

    async with engine.begin() as conn:
        for f in districts:
            props = f["properties"]
            code = props["code"]
            await conn.execute(
                text(
                    """
                    INSERT INTO andhra.districts (code, state_code, name_en, name_te, geom)
                    VALUES (:code, :state_code, :name_en, :name_te,
                            ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)::geography)
                    ON CONFLICT (code) DO UPDATE SET
                        state_code = EXCLUDED.state_code,
                        name_en = EXCLUDED.name_en,
                        name_te = EXCLUDED.name_te,
                        geom = EXCLUDED.geom
                    """
                ),
                {
                    "code": code,
                    "state_code": props["state_code"],
                    "name_en": props["name_en"],
                    "name_te": name_te.get(code, props["name_en"]),
                    "geom": json.dumps(f["geometry"]),
                },
            )
    return len(districts)


async def seed_places() -> int:
    places = json.load(open(DATA_DIR / "places_ap_od.json"))

    async with engine.begin() as conn:
        for p in places:
            await conn.execute(
                text(
                    """
                    INSERT INTO andhra.places (id, name_en, name_te, population, district_code, location)
                    VALUES (:id, :name_en, NULL, :population, NULL,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)
                    ON CONFLICT (id) DO UPDATE SET
                        name_en = EXCLUDED.name_en,
                        population = EXCLUDED.population,
                        location = EXCLUDED.location
                    """
                ),
                {
                    "id": p["id"],
                    "name_en": p["name_en"],
                    "population": p["population"],
                    "lon": p["lon"],
                    "lat": p["lat"],
                },
            )
    return len(places)


async def main() -> None:
    n_districts = await seed_districts()
    n_places = await seed_places()
    print(f"seeded {n_districts} districts, {n_places} places")


if __name__ == "__main__":
    asyncio.run(main())
