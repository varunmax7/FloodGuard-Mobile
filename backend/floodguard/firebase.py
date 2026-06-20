"""
Firebase Admin SDK initialisation + ID-token verification.

Dev mode (no credentials configured):
    id_token is treated as the raw E.164 phone number — no Firebase call made.
    This lets all auth tests run without a service-account file.

Production:
    Set FIREBASE_CREDENTIALS_PATH (path to JSON file)
    OR FIREBASE_CREDENTIALS_JSON (inline JSON string) in the environment.
"""
import json
import logging
import os

logger = logging.getLogger("floodguard")

_app = None          # firebase_admin App instance
_dev_mode = False    # True when no credentials are available
_initialised = False


def _init() -> None:
    global _app, _dev_mode, _initialised
    if _initialised:
        return

    import firebase_admin
    from firebase_admin import credentials

    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "").strip()
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON", "").strip()

    cred = None
    if cred_path and os.path.isfile(cred_path):
        cred = credentials.Certificate(cred_path)
        logger.info("Firebase: loading credentials from file %s", cred_path)
    elif cred_json:
        try:
            cred = credentials.Certificate(json.loads(cred_json))
            logger.info("Firebase: loading credentials from env JSON")
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Firebase: invalid FIREBASE_CREDENTIALS_JSON — %s", exc)

    if cred:
        try:
            _app = firebase_admin.get_app()
        except ValueError:
            _app = firebase_admin.initialize_app(cred)
        _dev_mode = False
    else:
        logger.warning(
            "Firebase: no credentials found — running in DEV MODE. "
            "id_token will be treated as a raw phone number. "
            "Set FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON for production."
        )
        _dev_mode = True

    _initialised = True


def verify_firebase_token(id_token: str) -> str:
    """
    Verify a Firebase ID token and return the E.164 phone number.

    Dev mode: id_token must itself be an E.164 phone number (e.g. +919999999999).
    Production: verifies against Firebase and extracts phone_number claim.
    """
    _init()

    if _dev_mode:
        token = id_token.strip()
        if not (token.startswith("+") and token[1:].isdigit() and 7 <= len(token) <= 16):
            raise ValueError(
                "DEV MODE — id_token must be an E.164 phone number (e.g. +919999999999). "
                "Configure Firebase credentials for production use."
            )
        return token

    from firebase_admin import auth as fb_auth

    try:
        decoded = fb_auth.verify_id_token(id_token, app=_app)
    except Exception as exc:
        raise ValueError(f"Firebase token verification failed: {exc}") from exc

    phone = decoded.get("phone_number")
    if not phone:
        raise ValueError("Firebase ID token has no phone_number claim.")
    return phone


def send_fcm_notification(
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> str | None:
    """
    Send a single FCM push notification.

    Returns the FCM message ID on success, or a dev-mode stub string.
    Raises on send failure (caller should handle and mark delivery FAILED).
    """
    _init()

    if _dev_mode:
        logger.info("FCM DEV MODE — would send to %s…: %s", token[:12], title)
        return f"dev-{token[:8]}"

    from firebase_admin import messaging

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        token=token,
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(content_available=True, sound="default"),
            )
        ),
    )

    return messaging.send(message, app=_app)  # returns message ID string
