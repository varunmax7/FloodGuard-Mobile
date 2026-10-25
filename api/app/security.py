import hashlib
import hmac


def hash_device_id(raw_device_id: str, key: str) -> bytes:
    """HMAC-SHA256(device_uuid, DEVICE_HASH_KEY) — §6.2 devices.device_hash."""
    return hmac.new(key.encode(), raw_device_id.encode(), hashlib.sha256).digest()
