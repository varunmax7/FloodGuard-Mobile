"""adminapi/views.py — stub."""
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_feeds(request):
    return Response({"detail": "Phase 10"}, status=501)
