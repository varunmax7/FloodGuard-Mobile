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
    LoginSerializer,
    RegisterSerializer,
    SavedPlacePatchSerializer,
    SavedPlaceSerializer,
    _normalize_phone,
)

logger = logging.getLogger("floodguard")


class AuthThrottle(AnonRateThrottle):
    scope = "otp_verify"  # reuse the tighter rate-limit bucket


def _issue_tokens(user, fcm_token: str, created: bool):
    if fcm_token and user.fcm_token != fcm_token:
        user.fcm_token = fcm_token
        user.save(update_fields=["fcm_token"])
    refresh = RefreshToken.for_user(user)
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {"id": str(user.id), "phone": user.phone, "created": created},
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register(request):
    """
    POST /api/v1/auth/register/
    Body: {phone, password, fcm_token?}
    Creates a new user with a hashed password and returns JWT access+refresh.
    """
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    phone = _normalize_phone(serializer.validated_data["phone"])
    password = serializer.validated_data["password"]
    fcm_token = serializer.validated_data.get("fcm_token", "")

    if User.objects.filter(phone=phone).exists():
        return Response(
            {"detail": "An account with this phone number already exists. Log in instead."},
            status=status.HTTP_409_CONFLICT,
        )
    user = User.objects.create_user(phone=phone, password=password)
    return _issue_tokens(user, fcm_token, created=True)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login(request):
    """
    POST /api/v1/auth/login/
    Body: {phone, password, fcm_token?}
    Validates credentials and returns JWT access+refresh.
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    phone = _normalize_phone(serializer.validated_data["phone"])
    password = serializer.validated_data["password"]
    fcm_token = serializer.validated_data.get("fcm_token", "")

    try:
        user = User.objects.get(phone=phone)
    except User.DoesNotExist:
        return Response({"detail": "Invalid phone number or password."}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.is_active or not user.check_password(password):
        return Response({"detail": "Invalid phone number or password."}, status=status.HTTP_401_UNAUTHORIZED)

    return _issue_tokens(user, fcm_token, created=False)


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
