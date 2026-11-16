"""Whether this PC is the administrator's: the admin secret and a server address, both from the .env file."""

from pathlib import Path
from typing import NamedTuple

from opendofusdata.env_file import admin_secret
from opendofusdata.sync_client import resolve_server_url


class AdminSettings(NamedTuple):
    """What the Administration tab needs; the secret is never logged or shown."""

    secret: str
    server_url: str


def load_admin_settings(env_path: Path) -> AdminSettings | None:
    """The settings when the .env holds a valid secret and an address is known, else None (no tab)."""
    secret = admin_secret(env_path)
    server_url = resolve_server_url(env_path)
    return AdminSettings(secret, server_url) if secret and server_url else None
