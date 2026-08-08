"""Helpers to resolve a stored FloodReport.photo_url value into a usable URL.

Photos are uploaded to S3 with a private ACL. Presigned URLs expire (default 1 h),
so we can't store a signed URL permanently in the DB — we regenerate one on read.

For legacy rows that stored a broken `http://.../media/reports/<key>` URL
(before this fix), we extract the S3 key from the path and sign that.
"""
from django.core.files.storage import default_storage


def _extract_key(stored: str) -> str:
    """
    Normalize whatever is in FloodReport.photo_url to an S3 key.

    - "reports/uuid.jpg"                     → "reports/uuid.jpg"          (already a key)
    - "http://.../media/reports/uuid.jpg"    → "reports/uuid.jpg"          (legacy broken URL)
    - "https://bucket.s3.amazonaws.com/reports/uuid.jpg?X-Amz-..."
                                              → "reports/uuid.jpg"          (previously signed URL)
    - ""                                      → ""
    """
    if not stored:
        return ""
    if not stored.startswith(("http://", "https://")):
        return stored.lstrip("/")
    # URL — pull the path, strip query string and any /media prefix, keep from reports/
    path = stored.split("?", 1)[0]
    # drop scheme + host
    slash_slash = path.find("//")
    if slash_slash != -1:
        path = path[slash_slash + 2:]
    first_slash = path.find("/")
    if first_slash != -1:
        path = path[first_slash + 1:]
    if path.startswith("media/"):
        path = path[len("media/"):]
    return path.lstrip("/")


def resolve_photo_url(stored: str) -> str:
    """Return a fresh presigned S3 URL for a stored photo_url value, or ''."""
    key = _extract_key(stored)
    if not key:
        return ""
    try:
        return default_storage.url(key)
    except Exception:
        return ""
