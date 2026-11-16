"""Server settings read from the environment: the server never starts without a real secret."""

from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from keyserver.signed_keys import MIN_SECRET_LENGTH

SECRET_VARIABLE = "KEY_SECRET"
DATABASE_VARIABLE = "KEYSERVER_DB"
ALLOWED_HOSTS_VARIABLE = "KEYSERVER_ALLOWED_HOSTS"
INTERNAL_HOST = "keyserver.internal"  # the only Host header accepted unless KEYSERVER_ALLOWED_HOSTS adds more
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "keys.db"


class SettingsError(Exception):
    """The environment cannot run the server (the message never contains the secret)."""


class Settings(NamedTuple):
    """Where the revocation list lives and the master secret that signs the keys."""

    db_path: Path
    key_secret: str
    allowed_hosts: tuple[str, ...] = (INTERNAL_HOST,)


def load_settings(environ: Mapping[str, str]) -> Settings:
    """Read the settings; raise SettingsError when the secret is missing, blank or too short."""
    secret = environ.get(SECRET_VARIABLE, "").strip()
    if len(secret) < MIN_SECRET_LENGTH:
        raise SettingsError(
            f"{SECRET_VARIABLE} absent ou trop court (au moins {MIN_SECRET_LENGTH} caractères) : "
            "génère-en un avec `python -m keyserver new-secret`")
    database = environ.get(DATABASE_VARIABLE, "").strip()
    hosts = tuple(host.strip() for host in environ.get(ALLOWED_HOSTS_VARIABLE, "").split(",") if host.strip())
    return Settings(Path(database) if database else DEFAULT_DATABASE_PATH, secret, hosts or (INTERNAL_HOST,))
