import ipaddress
import re
from functools import lru_cache
from urllib.parse import urlsplit

import boto3
from botocore.config import Config

from app.config import get_settings


@lru_cache
def s3_client():
    settings = get_settings()
    # SigV4 is pinned here too, even though this client only uploads/downloads:
    # a custom endpoint_url makes botocore presign with legacy SigV2, which
    # ap-south-1 rejects with "please use AWS4-HMAC-SHA256" (HTTP 400). Pinning
    # it means no presign path off this client can emit an unusable URL.
    kwargs = {
        "endpoint_url": settings.s3_endpoint_url,
        "config": Config(signature_version="s3v4"),
        "region_name": settings.aws_region,
    }
    # In production (AWS), omit credentials to use IAM role.
    # In dev (minio), provide explicit credentials.
    if settings.s3_access_key and settings.s3_secret_key:
        kwargs["aws_access_key_id"] = settings.s3_access_key
        kwargs["aws_secret_access_key"] = settings.s3_secret_key
    return boto3.client("s3", **kwargs)


@lru_cache
def _presign_client(endpoint_override: str | None = None):
    """Separate client for presigned GET URLs.

    s3_client() above points at a custom endpoint (minio in dev, an internal
    AWS endpoint in prod) — overriding endpoint_url makes botocore fall back
    to legacy SigV2 query auth, which S3 rejects outright. Force SigV4
    explicitly here. In prod, skip the custom endpoint too so boto3's normal
    virtual-hosted-style S3 resolution applies (the link must be fetchable
    from a browser); in dev, presign against minio's own public port —
    optionally with the hostname swapped for whatever host the viewer's
    browser actually used (see presigned_get_url's public_host).
    """
    settings = get_settings()
    kwargs: dict = {"config": Config(signature_version="s3v4"), "region_name": settings.aws_region}
    if settings.app_env != "prod":
        kwargs["endpoint_url"] = endpoint_override or settings.s3_public_endpoint_url
    if settings.s3_access_key and settings.s3_secret_key:
        kwargs["aws_access_key_id"] = settings.s3_access_key
        kwargs["aws_secret_access_key"] = settings.s3_secret_key
    return boto3.client("s3", **kwargs)


def put_object(bucket: str, key: str, data: bytes, content_type: str) -> None:
    s3_client().put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)


def get_object_bytes(bucket: str, key: str) -> bytes:
    return s3_client().get_object(Bucket=bucket, Key=key)["Body"].read()


# urlsplit().hostname is already lowercased and bracket-stripped at this point.
_HOSTNAME_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOSTNAME_RE = re.compile(rf"{_HOSTNAME_LABEL}(?:\.{_HOSTNAME_LABEL})*")


def _is_valid_host(hostname: str) -> bool:
    if ":" in hostname:  # IPv6 literal
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            return False
        return True
    return _HOSTNAME_RE.fullmatch(hostname) is not None


def _public_endpoint_for_host(public_host: str) -> str | None:
    """Rebuild S3_PUBLIC_ENDPOINT_URL around the host the viewer's browser used.

    The Host header is client-controlled, so anything unparseable or unexpected
    returns None and the caller falls back to the configured endpoint — a bad
    header must never reach boto3 (an IPv6 Host like "[::1]:8000" raised
    ValueError and 500'd the endpoint) or steer links at an arbitrary host.
    Only swaps when the configured endpoint names an explicit port, i.e. the
    dev minio case; otherwise the request host's :80/:443 is not minio.
    """
    try:
        hostname = urlsplit(f"//{public_host}").hostname
    except ValueError:
        return None
    if not hostname or len(hostname) > 253 or not _is_valid_host(hostname):
        return None
    parsed = urlsplit(get_settings().s3_public_endpoint_url)
    if not parsed.scheme or not parsed.port:
        return None
    literal = f"[{hostname}]" if ":" in hostname else hostname
    return f"{parsed.scheme}://{literal}:{parsed.port}"


def presigned_get_url(bucket: str, key: str, expires_in: int = 3600, public_host: str | None = None) -> str:
    """public_host (the incoming request's Host header, e.g. "192.168.1.23:5173")
    lets dev presign against the hostname the viewer's own browser used to reach
    the app, instead of the API server's hardcoded S3_PUBLIC_ENDPOINT_URL host.

    Without this, a phone opening the dev server over the LAN gets report JSON
    fine (it goes through Vite's same-origin proxy) but every photo_url says
    "http://localhost:9010/...", which on the phone resolves to the phone
    itself, not the dev machine — so the photo silently fails to load while
    everything else in the UI renders. Swapping in the request's own hostname
    (keeping the configured scheme/port) fixes that; prod is unaffected since
    it never uses this override (see _presign_client).
    """
    endpoint_override = None
    if public_host and get_settings().app_env != "prod":
        endpoint_override = _public_endpoint_for_host(public_host)
    return _presign_client(endpoint_override).generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
    )
