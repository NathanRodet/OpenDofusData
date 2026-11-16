"""Revoke a key on the server from the administrator's PC (the admin token travels, never the secret)."""

from typing import NamedTuple

from opendofusdata.admin_keys import admin_token
from opendofusdata.https_json import HttpsFailure, request_json
from opendofusdata.sync_client import FAILURE_MESSAGES, HTTP_OK, HTTP_UNAUTHORIZED, UNEXPECTED_MESSAGE

REVOKE_PATH = "/admin/revoke"
REVOKED_MESSAGE = "Clé révoquée"
PURGED_MESSAGE = "Clé révoquée, {count} relevé(s) supprimé(s)"
NOTHING_TO_PURGE_MESSAGE = "Clé révoquée, aucun relevé à supprimer"
SECRET_REFUSED_MESSAGE = "Secret d'administration refusé par le serveur"


class RevokeResult(NamedTuple):
    """Whether the server revoked the key, and what to tell the administrator."""

    ok: bool
    message: str


def _success_message(purge: bool, answer: dict[str, object]) -> str:
    """"Clé révoquée", with the number of deleted readings when the administrator asked for the purge."""
    purged = answer.get("purged")
    if not purge or isinstance(purged, bool) or not isinstance(purged, int):
        return REVOKED_MESSAGE
    return PURGED_MESSAGE.format(count=purged) if purged else NOTHING_TO_PURGE_MESSAGE


def revoke_key(base_url: str, secret: str, key_id: str, purge: bool = False) -> RevokeResult:
    """Ask the server to revoke this key identifier, and to delete its readings when `purge` is true."""
    request = {"key_id": key_id, **({"purge": True} if purge else {})}
    try:
        status, body = request_json(base_url, "POST", REVOKE_PATH, token=admin_token(secret), body=request)
    except HttpsFailure as failure:
        return RevokeResult(False, FAILURE_MESSAGES.get(failure.reason, UNEXPECTED_MESSAGE))
    if status == HTTP_OK and body.get("revoked") is True:
        return RevokeResult(True, _success_message(purge, body))
    if status == HTTP_UNAUTHORIZED:
        return RevokeResult(False, SECRET_REFUSED_MESSAGE)
    return RevokeResult(False, UNEXPECTED_MESSAGE)
