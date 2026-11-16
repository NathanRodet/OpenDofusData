"""Keys generated on the administrator's PC: the same maths as the server (src/server/keyserver/signed_keys.py)."""

import base64
import hashlib
import hmac
import re
import secrets

KEY_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{11}")
KEY_PREFIX = "odk1"
KEY_ID_BYTES = 8
KEY_PART_SEPARATOR = "."
ADMIN_LABEL = b"odk1-admin"


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign(secret: str, message: bytes) -> str:
    return _encode(hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest())


def new_key_id() -> str:
    """A random key identifier (11 URL-safe characters)."""
    return _encode(secrets.token_bytes(KEY_ID_BYTES))


def make_key(secret: str, key_id: str) -> str:
    """The key for this identifier, signed with the secret: `odk1.<id>.<signature>`."""
    signed_part = f"{KEY_PREFIX}{KEY_PART_SEPARATOR}{key_id}"
    return f"{signed_part}{KEY_PART_SEPARATOR}{_sign(secret, signed_part.encode('ascii'))}"


def admin_token(secret: str) -> str:
    """The token that authorises revocations; the master secret itself never leaves the PC."""
    return _sign(secret, ADMIN_LABEL)
