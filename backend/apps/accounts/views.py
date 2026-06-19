"""accounts/views.py — Auth, SavedPlace, DeviceToken views."""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SavedPlace, User
from .serializers import (
    DeviceTokenSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    SavedPlacePatchSerializer,
    SavedPlaceSerializer,
)

logger = logging.getLogger("floodguard")


# ── Throttle classes ──────────────────────────────────────────────────────────

class OtpRequestThrottle(AnonRateThrottle):
    scope = "otp_request"


class OtpVerifyThrottle(AnonRateThrottle):
    scope = "otp_verify"


# ── Auth endpoints ────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([OtpRequestThrottle])
def otp_request(request):
    """
    POST /api/v1/auth/otp/request

    Firebase phone OTP is initiated entirely on the client (Flutter Firebase SDK).
    This endpoint validates the phone format and returns a confirmation.
    The client uses the returned request_id as a correlation handle only.
    """
    serializer = OtpRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response({
        "request_id": "firebase-client-side",
        "detail": "Initiate phone OTP via the Firebase client SDK, then POST the ID token to /auth/otp/verify.",
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([OtpVerifyThrottle])
def otp_verify(request):
    """
    POST /api/v1/auth/otp/verify
    Body: {id_token, fcm_token?}

    Verifies the Firebase ID token, upserts the User record,
    stores the FCM token, and returns a SimpleJWT access+refresh pair.

    DEV MODE: when no Firebase credentials are configured, pass
    an E.164 phone number as id_token (e.g. +919999999999).
    """
    serializer = OtpVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    id_token = serializer.validated_data["id_token"]
    fcm_token = serializer.validated_data.get("fcm_token", "")

    try:
        from floodguard.firebase import verify_firebase_token
        phone = verify_firebase_token(id_token)
    except ValueError as exc:
        logger.warning("Auth token rejected: %s", exc)
        return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

    user, created = User.objects.get_or_create(phone=phone)
    if fcm_token and user.fcm_token != fcm_token:
        user.fcm_token = fcm_token
        user.save(update_fields=["fcm_token"])

    refresh = RefreshToken.for_user(user)
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "id": str(user.id),
            "phone": user.phone,
            "created": created,
        },
    }, status=status.HTTP_200_OK)


# ── Saved Places ──────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def places_list(request):
    """
    GET  /api/v1/places/ → list caller's saved places
    POST /api/v1/places/ → create a saved place (snaps to nearest H3 hex)
    """
    if request.method == "GET":
        qs = SavedPlace.objects.filter(user=request.user).select_related("hex")
        serializer = SavedPlaceSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    serializer = SavedPlaceSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    place = serializer.save()
    return Response(
        SavedPlaceSerializer(place, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def place_detail(request, pk):
    """PATCH /api/v1/places/{id}/ — toggle notify (only field updatable)."""
    try:
        place = SavedPlace.objects.get(pk=pk, user=request.user)
    except SavedPlace.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = SavedPlacePatchSerializer(place, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ── Device token ──────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_device_token(request):
    """POST /api/v1/devices/token — register or refresh FCM push token."""
    serializer = DeviceTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    fcm_token = serializer.validated_data["fcm_token"]
    request.user.fcm_token = fcm_token
    request.user.save(update_fields=["fcm_token"])
    return Response(status=status.HTTP_204_NO_CONTENT)
