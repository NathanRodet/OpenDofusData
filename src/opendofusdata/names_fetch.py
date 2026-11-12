"""One-off download of the item index from the public DofusDB API (stdlib only)."""

import http.client
import json
import math
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from opendofusdata.names_build import (
    NamesFetchError,
    UNEXPECTED_SHAPE_MESSAGE,
    build_entries,
    build_type_names,
    write_items_csv,
)

API_BASE_URL = "https://api.dofusdb.fr"
USER_AGENT = "OpenDofusData/1 (local price tool)"
ITEM_TYPES_PATH = "/item-types"
ITEMS_PATH = "/items"
TYPES_SELECT = "&$select[]=id&$select[]=name"
ITEMS_SELECT = "&$select[]=id&$select[]=name&$select[]=level&$select[]=typeId&$select[]=recyclingNuggets"
PAGE_SIZE = 50
REQUEST_DELAY_SECONDS = 0.15
REQUEST_TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 1.0
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
PROGRESS_EVERY_PAGES = 20
HTTP_TOO_MANY_REQUESTS = 429
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR_FIRST = 500
HTTP_REDIRECT_FIRST = 300
HTTP_REDIRECT_END = 400
MAX_COLLECTION_ITEMS = 200_000
PAGE_LIMIT_MARGIN = 2

FetchJson = Callable[[str], object]
Sleep = Callable[[float], None]
Progress = Callable[[str], None]


class TransientFetchError(Exception):
    """A temporary failure (network, HTTP 429 or 5xx) worth retrying."""


class NotFoundFetchError(NamesFetchError):
    """The server answered HTTP 404: the resource does not exist (yet)."""


@dataclass(frozen=True)
class FetchSummary:
    """What the download produced."""

    rows: int
    skipped: int
    duplicates: int
    path: Path
    size_bytes: int


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect, so the request can only ever reach the fixed API host."""

    def redirect_request(self, *arguments: object, **keywords: object) -> None:
        return None


OPENER = urllib.request.build_opener(NoRedirectHandler)


def _classify_http_error(error: urllib.error.HTTPError) -> Exception:
    if HTTP_REDIRECT_FIRST <= error.code < HTTP_REDIRECT_END:
        return NamesFetchError(
            f"Téléchargement impossible : l'API a demandé une redirection (HTTP {error.code}), refusée.")
    if error.code == HTTP_NOT_FOUND:
        return NotFoundFetchError(f"Téléchargement impossible : l'API a répondu HTTP {error.code}.")
    if error.code == HTTP_TOO_MANY_REQUESTS or error.code >= HTTP_SERVER_ERROR_FIRST:
        return TransientFetchError(f"HTTP {error.code}")
    return NamesFetchError(f"Téléchargement impossible : l'API a répondu HTTP {error.code}.")


def _parse_json(body: bytes) -> object:
    if len(body) > MAX_RESPONSE_BYTES:
        raise NamesFetchError("Réponse de l'API trop volumineuse.")
    try:
        return json.loads(body)
    except (ValueError, RecursionError) as error:
        raise NamesFetchError("Réponse de l'API illisible (JSON invalide).") from error


def http_get_json(url: str) -> object:
    """GET a URL and return the parsed JSON, raising TransientFetchError when retryable."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise _classify_http_error(error) from error
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError) as error:
        raise TransientFetchError(str(error)) from error
    return _parse_json(body)


class Requester:
    """Polite requester: pause between requests, retry transient failures with backoff."""

    def __init__(self, fetch: FetchJson, sleep: Sleep, delay: float) -> None:
        self._fetch = fetch
        self._sleep = sleep
        self._delay = delay
        self._requested = False

    def get(self, url: str) -> object:
        """Fetch a URL, retrying temporary failures; raise NamesFetchError when it persists."""
        if self._requested and self._delay > 0:
            self._sleep(self._delay)
        self._requested = True
        return self._with_retries(url)

    def _with_retries(self, url: str) -> object:
        for attempt in range(MAX_ATTEMPTS):
            try:
                return self._fetch(url)
            except TransientFetchError as error:
                last_error = error
                if attempt + 1 < MAX_ATTEMPTS:
                    self._sleep(RETRY_BACKOFF_SECONDS * 2 ** attempt)
        raise NamesFetchError(
            f"Téléchargement impossible : échec après {MAX_ATTEMPTS} essais ({last_error}).")


def _validated_page(payload: object) -> tuple[int, list[object]]:
    total = payload.get("total") if isinstance(payload, dict) else None
    data = payload.get("data") if isinstance(payload, dict) else None
    if (not isinstance(total, int) or isinstance(total, bool) or total < 0
            or not isinstance(data, list)):
        raise NamesFetchError(UNEXPECTED_SHAPE_MESSAGE.format(detail="pas de total ni de données"))
    return total, data


def _check_bounds(total: int, collected: int, path: str) -> None:
    if total > MAX_COLLECTION_ITEMS:
        raise NamesFetchError(f"Total annoncé trop grand pour {path} : {total}.")
    if collected > total:
        raise NamesFetchError(f"Nombre d'éléments inattendu pour {path} : "
                              f"{collected} reçus, {total} attendus.")


def _page_url(path: str, select: str, page_size: int, skip: int) -> str:
    return f"{API_BASE_URL}{path}?$limit={page_size}&$skip={skip}{select}"


def _report_progress(progress: Progress, label: str, page: int, total_pages: int) -> None:
    if page % PROGRESS_EVERY_PAGES == 0:
        progress(f"  {label} : {page}/{total_pages} pages téléchargées...")


def collect_all(requester: Requester, path: str, select: str, page_size: int,
                progress: Progress) -> list[object]:
    """Download every page of a collection and check the count against the API total."""
    collected: list[object] = []
    total = page = 0
    while page == 0 or (len(collected) < total and page_data):
        payload = requester.get(_page_url(path, select, page_size, len(collected)))
        total, page_data = _validated_page(payload)
        collected.extend(page_data)
        _check_bounds(total, len(collected), path)
        page += 1
        if page > MAX_COLLECTION_ITEMS // page_size + PAGE_LIMIT_MARGIN:
            raise NamesFetchError(f"Trop de pages demandées pour {path} : arrêt.")
        _report_progress(progress, path.strip("/"), page, math.ceil(total / page_size))
    if len(collected) != total:
        raise NamesFetchError(f"Nombre d'éléments inattendu pour {path} : "
                              f"{len(collected)} reçus, {total} attendus.")
    return collected


def download_item_names(
    output: Path, fetch: FetchJson = http_get_json, *, page_size: int = PAGE_SIZE,
    request_delay: float = REQUEST_DELAY_SECONDS, sleep: Sleep = time.sleep,
    progress: Progress = print,
) -> FetchSummary:
    """Download item types then items and write the CSV index atomically."""
    requester = Requester(fetch, sleep, request_delay)
    raw_types = collect_all(requester, ITEM_TYPES_PATH, TYPES_SELECT, page_size, progress)
    raw_items = collect_all(requester, ITEMS_PATH, ITEMS_SELECT, page_size, progress)
    result = build_entries(raw_items, build_type_names(raw_types))
    write_items_csv(result.entries, Path(output))
    return FetchSummary(len(result.entries), result.skipped, result.duplicates,
                        Path(output), Path(output).stat().st_size)
