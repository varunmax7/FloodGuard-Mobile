"""adminapi/permissions.py — role-based DRF permission classes."""
from rest_framework.permissions import BasePermission


class IsStaffAny(BasePermission):
    """Any authenticated staff user (ADMIN | OPERATOR | VIEWER)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsAdminRole(BasePermission):
    """ADMIN staff only — full write access."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.is_staff
            and request.user.role == "ADMIN"
        )


class IsOperatorOrAdmin(BasePermission):
    """OPERATOR or ADMIN — can trigger actions but not change calibration weights."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.is_staff
            and request.user.role in ("ADMIN", "OPERATOR")
        )


class CalibrationPermission(BasePermission):
    """
    GET  — any staff (VIEWER+).
    PUT/POST — ADMIN only.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_staff):
            return False
        if request.method in ("PUT", "POST", "PATCH", "DELETE"):
            return request.user.role == "ADMIN"
        return True
