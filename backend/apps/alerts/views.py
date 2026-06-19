"""alerts/views.py — stub."""
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def alerts_list(request):
    return Response([], status=200)
