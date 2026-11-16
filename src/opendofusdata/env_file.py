"""The client .env file (kept out of git): the admin secret and an optional server address."""

import logging
import re
from pathlib import Path
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

ADMIN_SECRET_NAME = "ADMIN_SECRET"
SERVER_URL_NAME = "SERVER_URL"
ENV_FILE_NAME = ".env"
MIN_SECRET_LENGTH = 43  # a secrets.token_urlsafe(32) value
HTTPS_SCHEME = "https"
QUOTE_CHARACTERS = "\"'"
UNSAFE_URL_CHARACTERS = frozenset("\\@?#")  # whitespace and control characters are already refused by isprintable()
MIN_PORT = 1
HOST_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
HOST_PATTERN = re.compile(rf"(?:{HOST_LABEL}\.)*{HOST_LABEL}")


def _unquote(value: str) -> str:
    """Drop one pair of matching single or double quotes around the value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in QUOTE_CHARACTERS:
        return value[1:-1]
    return value


def _parse_line(line: str) -> tuple[str, str] | None:
    """The (name, value) of a `NAME=value` line, or None for comments, blanks and malformed lines."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    name, _, value = stripped.partition("=")
    name = name.strip()
    return (name, _unquote(value.strip())) if name else None


def env_file_path(config_path: Path) -> Path:
    """The .env file sits next to config.json."""
    return config_path.parent / ENV_FILE_NAME


def read_env_file(path: Path) -> dict[str, str]:
    """Read the .env file; a missing or unreadable file gives an empty dict."""
    try:
        content = path.read_text(encoding="utf-8-sig")  # PowerShell and Notepad may add a BOM
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError) as error:
        logger.warning(".env illisible (%s : %s), ignoré", path, error)
        return {}
    pairs = (_parse_line(line) for line in content.splitlines())
    return dict(pair for pair in pairs if pair)


def admin_secret(path: Path) -> str | None:
    """The admin secret, or None when it is absent, blank or too short to be real."""
    secret = read_env_file(path).get(ADMIN_SECRET_NAME, "")
    if len(secret) < MIN_SECRET_LENGTH:
        if secret:
            logger.warning("%s trop court dans le .env, ignoré", ADMIN_SECRET_NAME)
        return None
    return secret


def _has_unsafe_characters(value: str) -> bool:
    """True for anything a URL parser and an HTTP client could read differently (space, control, backslash...)."""
    return not value.isascii() or not value.isprintable() or any(char in UNSAFE_URL_CHARACTERS for char in value)


def _canonical_origin(value: str) -> str | None:
    """`https://host[:port]` rebuilt from the parsed parts, or None when the value is not a bare https origin."""
    if _has_unsafe_characters(value):
        return None
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return None
    host = parts.hostname or ""
    if (parts.scheme != HTTPS_SCHEME or not HOST_PATTERN.fullmatch(host) or parts.path not in ("", "/")
            or parts.query or parts.fragment or (port is not None and port < MIN_PORT)):
        return None
    return f"{HTTPS_SCHEME}://{host}" + (f":{port}" if port is not None else "")


def server_url_override(path: Path) -> str | None:
    """The server address from the .env (https only, no path), rebuilt in canonical form, or None."""
    value = read_env_file(path).get(SERVER_URL_NAME, "")
    if not value:
        return None
    origin = _canonical_origin(value)
    if origin is None:
        logger.warning("%s invalide dans le .env (https://hôte[:port] attendu), ignoré", SERVER_URL_NAME)
    return origin
