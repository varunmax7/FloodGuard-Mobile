import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_device
from app.errors import APIError
from app.models import Device
from app.s3 import presigned_get_url

router = APIRouter(tags=["clusters"])
settings = get_settings()

# A cluster's "representative" report is the one whose photo/details stand in
# for the whole cluster on the live map — verified first, else most recent —
# skipping anything flagged for personal data or already purged (§10 retention).
_REPRESENTATIVE_REPORT_JOIN = """
    LEFT JOIN LATERAL (
        SELECT id, image_key, category, water_level, note, received_at, status
        FROM andhra.flood_reports r
        WHERE r.cluster_id = c.id
          AND r.status != 'rejected'
          AND r.contains_personal_data = false
          AND r.photo_deleted_at IS NULL
        ORDER BY (r.status = 'verified') DESC, r.received_at DESC
        LIMIT 1
    ) rep ON true
"""


@router.get("/clusters/nearby")
async def clusters_nearby(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: int = Query(default=5000, ge=100, le=50000),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            text(
                """
                SELECT id, ST_Y(centroid::geometry) lat, ST_X(centroid::geometry) lon,
                       ST_Distance(centroid, ST_GeogFromText(:pt)) distance_m,
                       report_count, unique_device_count,
                       (verified_count > 0) AS verified, is_hotspot,
                       CASE WHEN verified_count > 0 THEN 'verified' ELSE 'under_review' END AS status,
                       dominant_category,
                       EXTRACT(EPOCH FROM (now() - last_report_at)) / 60 AS minutes_ago
                FROM andhra.report_clusters
                WHERE status = 'active' AND ST_DWithin(centroid, ST_GeogFromText(:pt), :radius)
                ORDER BY centroid <-> ST_GeogFromText(:pt)
                LIMIT 20
                """
            ),
            {"pt": f"SRID=4326;POINT({lon} {lat})", "radius": radius_m},
        )
    ).mappings().all()

    return {
        "items": [
            {
                "id": str(r["id"]),
                "lat": round(r["lat"], 3),
                "lon": round(r["lon"], 3),
                "distance_m": round(r["distance_m"]),
                "report_count": r["report_count"],
                "unique_devices": r["unique_device_count"],
                "verified": r["verified"],
                "is_hotspot": r["is_hotspot"],
                "status": r["status"],
                "dominant_category": r["dominant_category"],
                "last_report_minutes_ago": round(r["minutes_ago"]),
            }
            for r in rows
        ]
    }


@router.get("/clusters/heat")
async def clusters_heat(
    request: Request,
    bbox: str = Query(..., description="west,south,east,north"),
    db: AsyncSession = Depends(get_db),
):
    w, s, e, n = (float(x) for x in bbox.split(","))
    rows = (
        await db.execute(
            text(
                f"""
                SELECT c.id, ST_Y(c.centroid::geometry) lat, ST_X(c.centroid::geometry) lon,
                       c.heat_weight, c.unique_device_count, c.verified_count, c.is_hotspot, c.last_report_at,
                       rep.image_key, rep.water_level
                FROM andhra.report_clusters c
                {_REPRESENTATIVE_REPORT_JOIN}
                WHERE c.status = 'active' AND c.heat_weight > 0.05
                  AND ST_Intersects(c.centroid, ST_MakeEnvelope(:w, :s, :e, :n, 4326)::geography)
                """
            ),
            {"w": w, "s": s, "e": e, "n": n},
        )
    ).mappings().all()
    return {
        "items": [
            {
                "id": str(r["id"]),
                "lat": r["lat"],
                "lon": r["lon"],
                "heat_weight": round(r["heat_weight"], 3),
                "unique_device_count": r["unique_device_count"],
                "verified_count": r["verified_count"],
                "is_hotspot": r["is_hotspot"],
                "last_report_at": r["last_report_at"].isoformat(),
                "water_level": r["water_level"],
                # Short-lived thumbnail URL for the map marker — re-fetched on
                # every /clusters/heat poll, so it never meaningfully expires
                # while the map stays open.
                "photo_url": presigned_get_url(
                    settings.photo_bucket, r["image_key"], expires_in=900, public_host=request.headers.get("host")
                ) if r["image_key"] else None,
            }
            for r in rows
        ]
    }


@router.get("/clusters/{cluster_id}/report")
async def cluster_report_detail(cluster_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Representative report for a cluster — what the live map's tap popup shows."""
    row = (
        await db.execute(
            text(
                f"""
                SELECT c.id, ST_Y(c.centroid::geometry) lat, ST_X(c.centroid::geometry) lon,
                       c.report_count, c.unique_device_count, c.verified_count, c.is_hotspot,
                       rep.image_key, rep.category, rep.water_level, rep.note, rep.received_at, rep.status
                FROM andhra.report_clusters c
                {_REPRESENTATIVE_REPORT_JOIN}
                WHERE c.id = :id AND c.status = 'active'
                """
            ),
            {"id": cluster_id},
        )
    ).mappings().first()
    if row is None:
        raise APIError(404, "NOT_FOUND", "Cluster not found.")
    return {
        "id": str(row["id"]),
        "lat": row["lat"],
        "lon": row["lon"],
        "report_count": row["report_count"],
        "unique_device_count": row["unique_device_count"],
        "verified": row["verified_count"] > 0,
        "is_hotspot": row["is_hotspot"],
        "category": row["category"],
        "water_level": row["water_level"],
        "note": row["note"],
        "observed_at": row["received_at"].isoformat() if row["received_at"] else None,
        "status": row["status"],
        "photo_url": presigned_get_url(
            settings.photo_bucket, row["image_key"], expires_in=900, public_host=request.headers.get("host")
        ) if row["image_key"] else None,
    }


@router.get("/clusters/geojson")
async def clusters_geojson(bbox: str = Query(...), db: AsyncSession = Depends(get_db)):
    w, s, e, n = (float(x) for x in bbox.split(","))
    rows = (
        await db.execute(
            text(
                """
                SELECT id, ST_Y(centroid::geometry) lat, ST_X(centroid::geometry) lon,
                       report_count, unique_device_count, is_hotspot,
                       CASE WHEN verified_count > 0 THEN 'verified' ELSE 'under_review' END AS status,
                       dominant_category
                FROM andhra.report_clusters
                WHERE status = 'active'
                  AND ST_Intersects(centroid, ST_MakeEnvelope(:w, :s, :e, :n, 4326)::geography)
                """
            ),
            {"w": w, "s": s, "e": e, "n": n},
        )
    ).mappings().all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                "properties": {
                    "id": str(r["id"]),
                    "report_count": r["report_count"],
                    "unique_devices": r["unique_device_count"],
                    "is_hotspot": r["is_hotspot"],
                    "status": r["status"],
                    "dominant_category": r["dominant_category"],
                },
            }
            for r in rows
        ],
    }


@router.post("/clusters/{cluster_id}/flag", status_code=202)
async def flag_cluster(
    cluster_id: uuid.UUID,
    reason: str,
    comment: str | None = None,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
):
    if reason not in {"not_flooding", "privacy", "offensive", "other"}:
        raise APIError(422, "INVALID_REASON", "Unknown flag reason.")
    await db.execute(
        text(
            "INSERT INTO andhra.misuse_reports (cluster_id, device_id, reason, comment) VALUES (:cid, :did, :reason, :comment)"
        ),
        {"cid": cluster_id, "did": device.id, "reason": reason, "comment": comment},
    )
    await db.commit()
    return {"status": "received"}
