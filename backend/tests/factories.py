"""Factory-boy factories for all core models."""
import uuid
from django.contrib.gis.geos import Point, Polygon
import factory
import factory.fuzzy

from apps.accounts.models import SavedPlace, User
from apps.alerts.models import AlertDelivery, AlertEvent
from apps.geo.models import AwsObservation, AwsStation, HexCell
from apps.reports.models import FloodReport, ModerationLog
from apps.risk.models import BiasFactor, CalibrationLog, RiskSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hex_polygon() -> Polygon:
    """Return a tiny square polygon near Hyderabad centre."""
    return Polygon(
        ((78.45, 17.38), (78.46, 17.38), (78.46, 17.39), (78.45, 17.39), (78.45, 17.38)),
        srid=4326,
    )


def _point(lng: float = 78.45, lat: float = 17.38) -> Point:
    return Point(lng, lat, srid=4326)


# ---------------------------------------------------------------------------
# Geo
# ---------------------------------------------------------------------------

class HexCellFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HexCell
        django_get_or_create = ("h3_index",)

    h3_index = factory.Sequence(lambda n: f"891f1d4f{n:07x}ff")  # fake but unique
    geom = factory.LazyFunction(_hex_polygon)
    centroid = factory.LazyFunction(_point)
    fsi_inputs = factory.LazyFunction(
        lambda: {
            "twi": 0.5,
            "depression_depth": 0.4,
            "hand": 0.3,
            "dist_to_water": 0.6,
            "slope": 0.2,
            "imperviousness": 0.7,
        }
    )
    fsi_score = 0.45
    ward_name = factory.Sequence(lambda n: f"Ward {n}")


class AwsStationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AwsStation
        django_get_or_create = ("station_id",)

    station_id = factory.Sequence(lambda n: f"HYD{n:04d}")
    name = factory.Sequence(lambda n: f"Station {n}")
    geom = factory.LazyFunction(_point)
    hex = factory.SubFactory(HexCellFactory)


class AwsObservationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AwsObservation

    station = factory.SubFactory(AwsStationFactory)
    ts = factory.Faker("date_time_this_month", tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata"))
    rain_1h = factory.fuzzy.FuzzyFloat(0.0, 30.0)
    rain_3h = factory.fuzzy.FuzzyFloat(0.0, 60.0)
    rain_24h = factory.fuzzy.FuzzyFloat(0.0, 120.0)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("phone",)

    phone = factory.Sequence(lambda n: f"+9190000{n:05d}")
    fcm_token = factory.Faker("sha256")
    is_active = True


class SavedPlaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SavedPlace

    user = factory.SubFactory(UserFactory)
    label = "HOME"
    geom = factory.LazyFunction(_point)
    hex = factory.SubFactory(HexCellFactory)
    notify = True


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

class RiskSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RiskSnapshot

    hex = factory.SubFactory(HexCellFactory)
    ts = factory.Faker("date_time_this_month", tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata"))
    rain_1h = factory.fuzzy.FuzzyFloat(0.0, 70.0)
    rain_3h = factory.fuzzy.FuzzyFloat(0.0, 100.0)
    rain_24h = factory.fuzzy.FuzzyFloat(0.0, 200.0)
    hazard_class = "MODERATE"
    risk_level = "MODERATE"
    confidence = factory.fuzzy.FuzzyInteger(50, 95)
    source_model = "ECMWF"


class BiasFactorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BiasFactor

    station_id = factory.Sequence(lambda n: f"HYD{n:04d}")
    region = ""
    multiplier = 1.0
    offset = 0.0
    valid_from = factory.Faker("date_time_this_year", tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata"))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class FloodReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FloodReport

    user = factory.SubFactory(UserFactory)
    geom = factory.LazyFunction(_point)
    hex = factory.SubFactory(HexCellFactory)
    photo_url = ""
    depth = "KNEE"
    road = "DIFFICULT"
    status = "PENDING"
    observed_at = factory.Faker("date_time_this_month", tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata"))
    client_uuid = factory.LazyFunction(uuid.uuid4)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AlertEvent

    hex = factory.SubFactory(HexCellFactory)
    risk_level = "HIGH"
    window_start = factory.Faker("date_time_this_month", tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata"))
    window_end = factory.Faker("date_time_this_month", tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata"))
    message = factory.Faker("sentence")


class AlertDeliveryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AlertDelivery

    alert = factory.SubFactory(AlertEventFactory)
    user = factory.SubFactory(UserFactory)
    status = "QUEUED"
