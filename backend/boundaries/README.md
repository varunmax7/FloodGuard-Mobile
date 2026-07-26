# Assam boundary data (filtered subset)

Assam-only subset of the Survey of India / data.gov.in administrative boundaries,
used by `manage.py load_assam_boundaries`.

- `states/DISTRICT_BOUNDARY.*`      — 35 Assam districts (POLYGON Z, LCC/metres)
- `talukas/SUBDISTRICT_BOUNDARY.*`  — 162 Assam sub-districts / revenue circles

Filtered from the full-India source (`E:/Dhanya/fg_app/boundaries`, ~618 MB) down
to `STATE_UT == "ASSAM"` (→ 9.4 MB) so the app ships with only the data it needs.
Geometry, attributes, `.prj` (LCC_WGS84) and `.cpg` are byte-preserved per feature;
the loader reprojects LCC→EPSG:4326 at load time. Verified: all 11 confirmed
flood-affected districts present with correct centroids, 162 talukas intact.

## Load

    cd backend
    python manage.py migrate
    python manage.py load_assam_boundaries --source ../boundaries   # adjust path

The full unfiltered India files remain at `E:/Dhanya/fg_app/boundaries` if ever needed.
