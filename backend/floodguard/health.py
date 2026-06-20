"""Liveness and readiness probe endpoints for Railway / k8s."""
import logging

from django.db import connections
from django.db.utils import OperationalError
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger("floodguard.health")


@api_view(["GET"])
@permission_classes([AllowAny])
def livez(request):
    """Always returns 200 while the process is alive."""
    return Response({"status": "alive"})


@api_view(["GET"])
@permission_classes([AllowAny])
def readyz(request):
    """Returns 200 only when DB + cache are reachable."""
    checks = {}
    ok = True

    # Database
    try:
        connections["default"].ensure_connection()
        checks["db"] = "ok"
    except OperationalError as exc:
        logger.error("readyz: DB unreachable — %s", exc)
        checks["db"] = "error"
        ok = False

    # Cache (Redis or LocMem — LocMem always succeeds)
    try:
        cache.set("_readyz_probe", "1", timeout=5)
        assert cache.get("_readyz_probe") == "1"
        checks["cache"] = "ok"
    except Exception as exc:
        logger.error("readyz: cache unreachable — %s", exc)
        checks["cache"] = "error"
        ok = False

    status = 200 if ok else 503
    return Response({"status": "ready" if ok else "unavailable", "checks": checks}, status=status)
