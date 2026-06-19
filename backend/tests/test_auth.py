"""Phase 2 tests — Auth (OTP/JWT) + SavedPlace + DeviceToken."""
import uuid
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import SavedPlace, User
from apps.geo.models import HexCell
from tests.factories import HexCellFactory, UserFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def auth_client(user: User) -> APIClient:
    """Return an APIClient with a valid JWT for the given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


# ---------------------------------------------------------------------------
# POST /api/v1/auth/otp/request
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOtpRequest:
    url = "/api/v1/auth/otp/request/"

    def test_valid_phone_returns_200(self):
        client = APIClient()
        resp = client.post(self.url, {"phone": "+919999999999"}, format="json")
        assert resp.status_code == 200
        assert "request_id" in resp.data

    def test_invalid_phone_returns_400(self):
        client = APIClient()
        resp = client.post(self.url, {"phone": "9999999999"}, format="json")  # no +
        assert resp.status_code == 400

    def test_missing_phone_returns_400(self):
        client = APIClient()
        resp = client.post(self.url, {}, format="json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/v1/auth/otp/verify  (DEV MODE — id_token = phone number)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOtpVerify:
    url = "/api/v1/auth/otp/verify/"

    def test_dev_mode_valid_phone_creates_user_and_returns_jwt(self):
        client = APIClient()
        phone = "+919876543210"
        resp = client.post(self.url, {"id_token": phone}, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert resp.data["user"]["phone"] == phone
        assert resp.data["user"]["created"] is True
        assert User.objects.filter(phone=phone).exists()

    def test_dev_mode_second_call_does_not_recreate_user(self):
        client = APIClient()
        phone = "+911234567890"
        client.post(self.url, {"id_token": phone}, format="json")
        resp = client.post(self.url, {"id_token": phone}, format="json")
        assert resp.status_code == 200
        assert resp.data["user"]["created"] is False
        assert User.objects.filter(phone=phone).count() == 1

    def test_dev_mode_stores_fcm_token(self):
        client = APIClient()
        phone = "+910000000001"
        fcm = "test-fcm-token-abc123"
        resp = client.post(self.url, {"id_token": phone, "fcm_token": fcm}, format="json")
        assert resp.status_code == 200
        assert User.objects.get(phone=phone).fcm_token == fcm

    def test_dev_mode_invalid_token_returns_401(self):
        client = APIClient()
        resp = client.post(self.url, {"id_token": "not-a-phone-number"}, format="json")
        assert resp.status_code == 401

    def test_dev_mode_missing_id_token_returns_400(self):
        client = APIClient()
        resp = client.post(self.url, {}, format="json")
        assert resp.status_code == 400

    def test_jwt_access_token_authenticates(self):
        """Token returned by verify must grant access to a protected endpoint."""
        client = APIClient()
        phone = "+910000000002"
        resp = client.post(self.url, {"id_token": phone}, format="json")
        access = resp.data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_resp = client.get("/api/v1/places/")
        assert me_resp.status_code == 200  # authenticated → 200 not 401


# ---------------------------------------------------------------------------
# GET + POST /api/v1/places/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPlaces:
    list_url = "/api/v1/places/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.list_url)
        assert resp.status_code == 401

    def test_list_returns_only_own_places(self, db):
        u1 = UserFactory(phone="+910000000010")
        u2 = UserFactory(phone="+910000000011")
        hex1 = HexCellFactory()

        SavedPlace.objects.create(user=u1, label="HOME", geom=hex1.centroid, hex=hex1, notify=True)
        SavedPlace.objects.create(user=u2, label="OFFICE", geom=hex1.centroid, hex=hex1, notify=True)

        resp = auth_client(u1).get(self.list_url)
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["label"] == "HOME"

    def test_create_snaps_to_correct_hex(self, db):
        """POSTing lat/lng must snap to an existing HexCell in the DB."""
        import h3
        user = UserFactory(phone="+910000000020")

        # Use a centroid of an existing hex
        hex_obj = HexCellFactory()
        lat = hex_obj.centroid.y
        lng = hex_obj.centroid.x

        resp = auth_client(user).post(
            self.list_url,
            {"label": "HOME", "lat": lat, "lng": lng, "notify": True},
            format="json",
        )
        assert resp.status_code == 201
        place = SavedPlace.objects.get(user=user)
        expected_h3 = h3.latlng_to_cell(lat, lng, 9)
        assert place.hex_id == expected_h3

    def test_create_returns_latitude_longitude(self, db):
        user = UserFactory(phone="+910000000021")
        hex_obj = HexCellFactory()
        lat, lng = hex_obj.centroid.y, hex_obj.centroid.x

        resp = auth_client(user).post(
            self.list_url,
            {"label": "OFFICE", "lat": lat, "lng": lng, "notify": False},
            format="json",
        )
        assert resp.status_code == 201
        assert "latitude" in resp.data
        assert "longitude" in resp.data
        assert abs(resp.data["latitude"] - lat) < 1e-6

    def test_create_invalid_label_returns_400(self, db):
        user = UserFactory(phone="+910000000022")
        resp = auth_client(user).post(
            self.list_url,
            {"label": "GYM", "lat": 17.38, "lng": 78.45, "notify": True},
            format="json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PATCH /api/v1/places/{id}/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPlacePatch:
    def _create_place(self, user, notify=True):
        hex_obj = HexCellFactory()
        return SavedPlace.objects.create(
            user=user, label="HOME", geom=hex_obj.centroid, hex=hex_obj, notify=notify
        )

    def test_toggle_notify_off(self, db):
        user = UserFactory(phone="+910000000030")
        place = self._create_place(user, notify=True)
        resp = auth_client(user).patch(f"/api/v1/places/{place.pk}/", {"notify": False}, format="json")
        assert resp.status_code == 200
        place.refresh_from_db()
        assert place.notify is False

    def test_toggle_notify_on(self, db):
        user = UserFactory(phone="+910000000031")
        place = self._create_place(user, notify=False)
        resp = auth_client(user).patch(f"/api/v1/places/{place.pk}/", {"notify": True}, format="json")
        assert resp.status_code == 200
        place.refresh_from_db()
        assert place.notify is True

    def test_cannot_patch_other_users_place(self, db):
        u1 = UserFactory(phone="+910000000032")
        u2 = UserFactory(phone="+910000000033")
        place = self._create_place(u1)
        resp = auth_client(u2).patch(f"/api/v1/places/{place.pk}/", {"notify": False}, format="json")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/devices/token
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeviceToken:
    url = "/api/v1/devices/token/"

    def test_registers_fcm_token(self, db):
        user = UserFactory(phone="+910000000040")
        new_token = "fcm-device-xyz-789"
        resp = auth_client(user).post(self.url, {"fcm_token": new_token}, format="json")
        assert resp.status_code == 204
        user.refresh_from_db()
        assert user.fcm_token == new_token

    def test_unauthenticated_returns_401(self):
        resp = APIClient().post(self.url, {"fcm_token": "abc"}, format="json")
        assert resp.status_code == 401

    def test_missing_fcm_token_returns_400(self, db):
        user = UserFactory(phone="+910000000041")
        resp = auth_client(user).post(self.url, {}, format="json")
        assert resp.status_code == 400
