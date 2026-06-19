"""Make Celery app available at package level."""
from .celery import app as celery_app

__all__ = ("celery_app",)
