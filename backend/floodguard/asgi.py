"""
ASGI config for the FloodGuard Django project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "floodguard.settings")
application = get_asgi_application()
