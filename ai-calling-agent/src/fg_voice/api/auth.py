"""Admin API-key authentication for the reports read + stream + export
endpoints.

The Twilio webhooks (`/voice/*`) authenticate via X-Twilio-Signature
(see `telephony/twilio_signature.py`); the health endpoints are
public. This module is only for the ops-facing report endpoints
that expose caller-report data.

Design:
- Header: `X-Admin-Api-Key`
- Setting: `ADMIN_API_KEY` — SecretStr, default empty. Empty MEANS
  auth is disabled (dev bypass) — a fresh clone can hit `/reports`
  without any config. In production, `require_production_secrets()`
  logs a boot warning when the key is empty so operators notice
- Constant-time comparison via `hmac.compare_digest` so timing
  attacks can't leak the key one character at a time
- Rejection uses 401 with a `WWW-Authenticate` header so browsers
  behave predictably; error body is intentionally minimal
- Applied via `Depends(require_admin_api_key)` on the endpoint — no
  global middleware, so it's obvious per-route which endpoints are
  guarded and which aren't"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from fg_voice.config import get_settings

ADMIN_API_KEY_HEADER = "X-Admin-Api-Key"


def require_admin_api_key(
    x_admin_api_key: Annotated[str | None, Header(alias=ADMIN_API_KEY_HEADER)] = None,
) -> None:
    """FastAPI dependency. Raises 401 on missing/wrong key when the
    setting is populated; no-op when the setting is empty.

    Returning None on success is deliberate — endpoints don't need
    the key value, just the fact that it was validated."""
    expected = get_settings().admin_api_key.get_secret_value()
    if not expected:
        # Dev bypass. `require_production_secrets` in config.py refuses
        # to boot production without the key set, so this branch is
        # only reachable in dev/staging.
        return
    if x_admin_api_key is None or not hmac.compare_digest(x_admin_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing admin API key",
            headers={"WWW-Authenticate": ADMIN_API_KEY_HEADER},
        )


# Convenience `Depends(...)` alias so route decorators stay short:
#   @router.get("/reports", dependencies=[AdminApiKey])
AdminApiKey = Depends(require_admin_api_key)


__all__ = ["ADMIN_API_KEY_HEADER", "AdminApiKey", "require_admin_api_key"]
