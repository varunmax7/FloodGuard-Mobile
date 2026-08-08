"""accounts/serializers.py — Auth, SavedPlace, DeviceToken serializers."""
import h3
from django.contrib.gis.geos import Point
from rest_framework import serializers

from apps.geo.models import HexCell
from .models import SavedPlace, User


_PHONE_REGEX = r"^\+?[1-9]\d{6,14}$"
_PHONE_ERR = {"invalid": "Enter a valid phone number (7-15 digits, optional leading +)."}


def _normalize_phone(raw: str) -> str:
    """Store all phones as E.164 (+<countrycode><number>). Assumes IN (+91) if bare."""
    s = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if s.startswith("+"):
        return s
    # 10-digit Indian mobile → prepend +91
    if len(s) == 10 and s[0] in "6789":
        return "+91" + s
    return "+" + s


class RegisterSerializer(serializers.Serializer):
    phone = serializers.RegexField(regex=_PHONE_REGEX, error_messages=_PHONE_ERR)
    password = serializers.CharField(min_length=6, max_length=128, write_only=True)
    fcm_token = serializers.CharField(required=False, allow_blank=True, default="")


class LoginSerializer(serializers.Serializer):
    phone = serializers.RegexField(regex=_PHONE_REGEX, error_messages=_PHONE_ERR)
    password = serializers.CharField(write_only=True)
    fcm_token = serializers.CharField(required=False, allow_blank=True, default="")


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "created_at"]


class SavedPlaceSerializer(serializers.ModelSerializer):
    """Used for GET list and POST create."""
    lat = serializers.FloatField(write_only=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(write_only=True, min_value=-180, max_value=180)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = SavedPlace
        fields = [
            "id", "label",
            "lat", "lng",           # write-only inputs
            "latitude", "longitude",  # read-only outputs
            "hex_id", "notify", "created_at",
        ]
        read_only_fields = ["id", "hex_id", "created_at", "latitude", "longitude"]

    def get_latitude(self, obj) -> float | None:
        return obj.geom.y if obj.geom else None

    def get_longitude(self, obj) -> float | None:
        return obj.geom.x if obj.geom else None

    def validate_label(self, value: str) -> str:
        value = value.upper()
        if value not in ("HOME", "OFFICE", "OTHER"):
            raise serializers.ValidationError("label must be HOME, OFFICE, or OTHER")
        return value

    def create(self, validated_data: dict) -> SavedPlace:
        from django.conf import settings as _settings
        lat = validated_data.pop("lat")
        lng = validated_data.pop("lng")

        geom = Point(lng, lat, srid=4326)
        h3_index = h3.latlng_to_cell(lat, lng, _settings.H3_RESOLUTION)
        hex_cell = HexCell.objects.filter(h3_index=h3_index).first()

        return SavedPlace.objects.create(
            user=self.context["request"].user,
            geom=geom,
            hex=hex_cell,
            **validated_data,
        )


class SavedPlacePatchSerializer(serializers.ModelSerializer):
    """PATCH /places/{id} — only notify is updatable."""
    class Meta:
        model = SavedPlace
        fields = ["id", "label", "latitude", "longitude", "hex_id", "notify", "created_at"]
        read_only_fields = ["id", "label", "hex_id", "created_at"]

    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    def get_latitude(self, obj) -> float | None:
        return obj.geom.y if obj.geom else None

    def get_longitude(self, obj) -> float | None:
        return obj.geom.x if obj.geom else None


class DeviceTokenSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(min_length=1)
