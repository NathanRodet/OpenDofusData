"""Revoke a key on the server from the administrator's PC (the admin token travels, never the secret)."""

from typing import NamedTuple

from opendofusdata.admin_keys import admin_token
from opendofusdata.https_json import HttpsFailure, request_json
from opendofusdata.sync_client import FAILURE_MESSAGES, HTTP_OK, HTTP_UNAUTHORIZED, UNEXPECTED_MESSAGE

REVOKE_PATH = "/admin/revoke"
REVOKED_MESSAGE = "Clé révoquée"
SECRET_REFUSED_MESSAGE = "Secret d'administration refusé par le serveur"


class RevokeResult(NamedTuple):
    """Whether the server revoked the key, and what to tell the administrator."""

    ok: bool
    message: str


def revoke_key(base_url: str, secret: str, key_id: str) -> RevokeResult:
    """Ask the server to revoke this key identifier."""
    try:
        status, body = request_json(base_url, "POST", REVOKE_PATH, token=admin_token(secret),
                                    body={"key_id": key_id})
    except HttpsFailure as failure:
        return RevokeResult(False, FAILURE_MESSAGES.get(failure.reason, UNEXPECTED_MESSAGE))
    if status == HTTP_OK and body.get("revoked") is True:
        return RevokeResult(True, REVOKED_MESSAGE)
    if status == HTTP_UNAUTHORIZED:
        return RevokeResult(False, SECRET_REFUSED_MESSAGE)
    return RevokeResult(False, UNEXPECTED_MESSAGE)
