"""geo/views.py — stub."""
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def hex_list(request):
    return Response({"detail": "Phase 1"}, status=501)
