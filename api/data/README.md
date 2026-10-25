# Reference data sources (§5 DS-6, DS-8, DS-9)

## `districts_ap_od.geojson` — DS-6 district boundaries

- **Source:** geoBoundaries IND ADM2 (`https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/`),
  commit `9469f09`, `sourceDataUpdateDate` 2023-01-19, `boundarySource`
  "Pathways Data Pvt. Ltd., lgdirectory.gov.in".
- **License:** Open Data Commons Open Database License (ODbL) 1.0 — attribution required, commercial use allowed.
- **Processing:** filtered from the full India ADM2 set (735 features) to the
  43 districts whose centroid falls inside the Andhra Pradesh or Odisha ADM1
  polygon (geoBoundaries IND ADM1, same release); the Yanam exclave
  (Puducherry UT, geographically inside AP) is excluded. Geometry simplified
  (tolerance 0.0008°, topology-preserving) to keep file size down.
- **Known limitation (same issue as `backend/boundaries/`, see project
  memory):** this reflects **pre-April-2022** Andhra Pradesh (13 districts),
  not the current 26-district structure (e.g. no separate "NTR district" —
  the DDL's own example code). Acceptable for an MVP where districts are
  used for display/grouping, not core geometry-critical logic; flagged here
  for a future re-cut against a post-2022 source (e.g. Survey of India open
  data) before this goes anywhere near production.
- **Regenerate:** see `scripts/filter_districts.py` reference logic (run
  outside the repo; not checked in as a script because it's a one-time data
  prep step, not part of the running app).

## `places_ap_od.json` — DS-8 place names

- **Source:** GeoNames `IN.zip` (`https://download.geonames.org/export/dump/IN.zip`).
- **License:** CC BY 4.0 — attribution required.
- **Processing:** filtered to feature class `P` (populated place), population
  ≥ 3,000, centroid inside the AP or Odisha ADM1 polygon → 475 places.

## `district_name_te.json` — DS-9 Telugu district names

**DRAFT — native-speaker review required before launch** (spec §7.14, R-4,
AT-27), same as every other Telugu string in this build. AP names are
standard Telugu usage; the 30 Odisha names are best-effort phonetic
transliterations (Odisha is not a Telugu-speaking state) and need the most
scrutiny of anything in this file.

## Attribution string (used wherever district/place data appears)

> District boundaries: geoBoundaries (ODbL 1.0). Place names: GeoNames (CC BY 4.0).
