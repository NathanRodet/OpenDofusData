"""Download an update executable and verify its SHA-256 before it may replace the running one."""

import hashlib
import hmac
import http.client
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from opendofusdata.names_fetch import USER_AGENT
from opendofusdata.updates import UpdateInfo, is_allowed_url

MEGABYTE = 1024 * 1024
MAX_EXE_BYTES = 200 * MEGABYTE
MAX_CHECKSUM_BYTES = 4096
REQUEST_TIMEOUT_SECONDS = 60
CHUNK_BYTES = MEGABYTE
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
TARGET_NAME = "OpenDofusData-{version}.exe.new"
NOT_INSTALLABLE_MESSAGE = "Cette version n'est pas installable automatiquement (fichier ou somme de contrôle absent)."
BAD_CHECKSUM_MESSAGE = "La somme de contrôle publiée est illisible."
MISMATCH_MESSAGE = "La somme de contrôle du fichier téléchargé ne correspond pas : téléchargement refusé."
REFUSED_URL_MESSAGE = "Adresse de téléchargement refusée : {url}"
TOO_LARGE_MESSAGE = "Fichier trop volumineux : téléchargement refusé."
DOWNLOAD_FAILED_MESSAGE = "Téléchargement impossible : {error}"
FetchBytes = Callable[[str, int], bytes]


class UpdateError(Exception):
    """An update step failed; the message is in French and meant for the player."""


class AllowedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follows redirects (GitHub serves assets from another host) only to allowed hosts."""

    def redirect_request(self, request, file, code, message, headers, new_url):
        if not is_allowed_url(new_url):
            raise UpdateError(REFUSED_URL_MESSAGE.format(url=new_url))
        return super().redirect_request(request, file, code, message, headers, new_url)


OPENER = urllib.request.build_opener(AllowedRedirectHandler)


def http_get_bytes(url: str, max_bytes: int) -> bytes:
    """GET an allowed HTTPS URL and return its body, refusing anything above `max_bytes`."""
    if not is_allowed_url(url):
        raise UpdateError(REFUSED_URL_MESSAGE.format(url=url))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read(max_bytes + 1)
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError) as error:
        raise UpdateError(DOWNLOAD_FAILED_MESSAGE.format(error=error)) from error
    if len(body) > max_bytes:
        raise UpdateError(TOO_LARGE_MESSAGE)
    return body


def parse_checksum(text: str) -> str | None:
    """The first token of a `sha256sum`-style file when it is 64 hex digits, lowercased."""
    tokens = text.split()
    return tokens[0].lower() if tokens and SHA256_PATTERN.match(tokens[0]) else None


def _write_atomically(directory: Path, name: str, data: bytes) -> Path:
    target = directory / name
    temporary = directory / (name + ".part")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def download_update(info: UpdateInfo, directory: Path, fetch: FetchBytes = http_get_bytes) -> Path:
    """Download the executable, check its SHA-256 against the published one, return its path."""
    if not info.can_install:
        raise UpdateError(NOT_INSTALLABLE_MESSAGE)
    expected = parse_checksum(fetch(info.checksum_url, MAX_CHECKSUM_BYTES).decode("utf-8", "replace"))
    if expected is None:
        raise UpdateError(BAD_CHECKSUM_MESSAGE)
    data = fetch(info.exe_url, MAX_EXE_BYTES)
    if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), expected):
        raise UpdateError(MISMATCH_MESSAGE)
    return _write_atomically(directory, TARGET_NAME.format(version=info.version), data)
