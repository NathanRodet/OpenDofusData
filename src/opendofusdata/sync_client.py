"""The connection test of the player: one GET /check with the key, answered in plain French."""

from pathlib import Path
from typing import NamedTuple

from opendofusdata.env_file import server_url_override
from opendofusdata.https_json import BAD_RESPONSE, INSECURE, REDIRECT, TIMEOUT, UNREACHABLE, HttpsFailure, request_json

DEFAULT_SERVER_URL = ""  # the official server address, to fill in once the domain exists
CHECK_PATH = "/check"
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
SUCCESS_MESSAGE = "Connexion réussie"
REFUSED_MESSAGE = "Clé refusée ou révoquée"
UNREACHABLE_MESSAGE = "Serveur injoignable"
UNEXPECTED_MESSAGE = "Réponse inattendue du serveur"
INSECURE_MESSAGE = "Adresse du serveur non sécurisée (https attendu)"
FAILURE_MESSAGES = {
    UNREACHABLE: UNREACHABLE_MESSAGE, TIMEOUT: UNREACHABLE_MESSAGE, REDIRECT: UNEXPECTED_MESSAGE,
    BAD_RESPONSE: UNEXPECTED_MESSAGE, INSECURE: INSECURE_MESSAGE,
}


class ConnectionResult(NamedTuple):
    """Whether the key works, and what to tell the player (never containing the key)."""

    ok: bool
    message: str


def resolve_server_url(env_path: Path) -> str | None:
    """The server address: the one in the .env if valid, else the built-in default, else None."""
    return server_url_override(env_path) or DEFAULT_SERVER_URL or None


def check_connection(base_url: str, key: str) -> ConnectionResult:
    """Ask the server whether this key is accepted; sends the key and nothing else."""
    try:
        status, body = request_json(base_url, "GET", CHECK_PATH, token=key)
    except HttpsFailure as failure:
        return ConnectionResult(False, FAILURE_MESSAGES.get(failure.reason, UNEXPECTED_MESSAGE))
    if status == HTTP_OK and body.get("status") == "ok":
        return ConnectionResult(True, SUCCESS_MESSAGE)
    if status == HTTP_UNAUTHORIZED:
        return ConnectionResult(False, REFUSED_MESSAGE)
    return ConnectionResult(False, UNEXPECTED_MESSAGE)
