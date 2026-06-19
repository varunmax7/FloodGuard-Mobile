"""accounts/serializers.py — Auth, SavedPlace, DeviceToken serializers."""
import h3
from django.contrib.gis.geos import Point
from rest_framework import serializers

from apps.geo.models import HexCell
from .models import SavedPlace, User


class OtpRequestSerializer(serializers.Serializer):
    phone = serializers.RegexField(
        regex=r"^\+[1-9]\d{6,14}$",
        error_messages={"invalid": "Phone must be in E.164 format, e.g. +919999999999"},
    )


class OtpVerifySerializer(serializers.Serializer):
    """
    id_token: Firebase ID token obtained after client-side phone OTP.
              In DEV MODE (no Firebase creds) pass the E.164 phone number directly.
    fcm_token: Optional FCM push token to register on login.
    """
    id_token = serializers.CharField()
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
        lat = validated_data.pop("lat")
        lng = validated_data.pop("lng")

        geom = Point(lng, lat, srid=4326)
        h3_index = h3.latlng_to_cell(lat, lng, 9)
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
