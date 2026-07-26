"""geo/models.py — HexCell, AwsStation, AwsObservation + District/Taluka (Assam scope)."""
from django.contrib.gis.db import models


class District(models.Model):
    """
    Administrative district. Populated from the Survey of India district
    boundary layer via the `load_assam_boundaries` management command.
    """
    name = models.CharField(max_length=64, unique=True)   # canonical name
    state = models.CharField(max_length=32, default="Assam")
    geom = models.MultiPolygonField(srid=4326)
    centroid = models.PointField(srid=4326)

    class Meta:
        db_table = "geo_district"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"District({self.name})"


class Taluka(models.Model):
    """
    Sub-district / revenue circle within a District. Names are not globally
    unique (e.g. two districts each have a "Sonari Circle"), so uniqueness is
    scoped to (district, name).
    """
    name = models.CharField(max_length=64)
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name="talukas")
    geom = models.MultiPolygonField(srid=4326)
    centroid = models.PointField(srid=4326)

    class Meta:
        db_table = "geo_taluka"
        ordering = ["district__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["district", "name"],
                                    name="geo_taluka_district_name_uniq"),
        ]
        indexes = [
            models.Index(fields=["district", "name"]),
        ]

    def __str__(self):
        return f"Taluka({self.name}, {self.district.name})"


class HexCell(models.Model):
    """H3 resolution-9 hexagon cell (~174m edge length)."""
    h3_index = models.CharField(max_length=20, primary_key=True)  # H3 cell index string
    geom = models.PolygonField(srid=4326, null=True, blank=True)  # boundary polygon
    centroid = models.PointField(srid=4326, null=True, blank=True)
    # FSI inputs stored as JSON
    fsi_inputs = models.JSONField(default=dict, blank=True)
    fsi_score = models.FloatField(default=0.0)  # 0..1
    ward_name = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "geo_hex_cell"
        indexes = [
            models.Index(fields=["fsi_score"]),
        ]

    def __str__(self):
        return f"HexCell({self.h3_index})"


class AwsStation(models.Model):
    """Automatic Weather Station (rain gauge)."""
    station_id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=200)
    geom = models.PointField(srid=4326)
    hex = models.ForeignKey(HexCell, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="stations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "geo_aws_station"

    def __str__(self):
        return f"{self.station_id} — {self.name}"


class AwsObservation(models.Model):
    """Observed rainfall readings from an AWS station."""
    station = models.ForeignKey(AwsStation, on_delete=models.CASCADE, related_name="observations")
    ts = models.DateTimeField(db_index=True)
    rain_1h = models.FloatField(null=True, blank=True)
    rain_3h = models.FloatField(null=True, blank=True)
    rain_24h = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "geo_aws_observation"
        ordering = ["-ts"]
        constraints = [
            models.UniqueConstraint(fields=["station", "ts"], name="geo_awsobs_station_ts_uniq"),
        ]
        indexes = [
            models.Index(fields=["station", "ts"]),
        ]

    def __str__(self):
        return f"Obs({self.station_id}, {self.ts})"
