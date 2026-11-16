"""Signed API keys: `odk1.<id>.<signature>`, the signature being an HMAC of the id with a master secret."""

import base64
import hashlib
import hmac
import re
import secrets

KEY_PREFIX = "odk1"
KEY_ID_BYTES = 8
SECRET_BYTES = 32
MIN_SECRET_LENGTH = 43  # the length of a secrets.token_urlsafe(32) value
ADMIN_LABEL = b"odk1-admin"
KEY_PATTERN = re.compile(r"^odk1\.[A-Za-z0-9_-]{11}\.[A-Za-z0-9_-]{43}$")
KEY_PART_SEPARATOR = "."
KEY_ID_INDEX = 1


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign(secret: str, message: bytes) -> str:
    return _encode(hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest())


def generate_secret() -> str:
    """A fresh master secret."""
    return secrets.token_urlsafe(SECRET_BYTES)


def new_key_id() -> str:
    """A random key identifier (11 URL-safe characters)."""
    return _encode(secrets.token_bytes(KEY_ID_BYTES))


def make_key(secret: str, key_id: str) -> str:
    """The key for this identifier, signed with the secret."""
    signed_part = f"{KEY_PREFIX}{KEY_PART_SEPARATOR}{key_id}"
    return f"{signed_part}{KEY_PART_SEPARATOR}{_sign(secret, signed_part.encode('ascii'))}"


def parse_key(key: str) -> str | None:
    """The identifier inside a well-formed key (format only, no signature check), else None."""
    if not KEY_PATTERN.fullmatch(key):
        return None
    return key.split(KEY_PART_SEPARATOR)[KEY_ID_INDEX]


def signature_is_valid(secret: str, key: str) -> bool:
    """True when the key is well formed and signed with this secret (constant-time comparison)."""
    key_id = parse_key(key)
    return key_id is not None and hmac.compare_digest(make_key(secret, key_id), key)


def admin_token(secret: str) -> str:
    """The token that authorises administration calls; the master secret itself never travels."""
    return _sign(secret, ADMIN_LABEL)
