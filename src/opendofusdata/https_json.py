"""One HTTPS JSON request: secure only, no redirect, bounded size, nothing secret in any error."""

import http.client
import json
import urllib.error
import urllib.request

from opendofusdata.names_fetch import OPENER

REQUEST_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 65_536
HTTPS_PREFIX = "https://"
USER_AGENT = "OpenDofusData"
REDIRECT_FIRST = 300
REDIRECT_END = 400
INSECURE = "insecure"
REDIRECT = "redirect"
TIMEOUT = "timeout"
UNREACHABLE = "unreachable"
BAD_RESPONSE = "bad_response"


class HttpsFailure(Exception):
    """The request could not be completed; `reason` is one of the codes above (never any secret)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _build_request(base_url: str, method: str, path: str, token: str | None,
                   body: dict[str, object] | None) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    return urllib.request.Request(base_url + path, data=data, headers=headers, method=method)


def _parse_object(body: bytes) -> dict[str, object]:
    """The JSON object in the body; BAD_RESPONSE when it is too big, not JSON or not an object."""
    if len(body) > MAX_RESPONSE_BYTES:
        raise HttpsFailure(BAD_RESPONSE)
    try:
        parsed = json.loads(body)
    except (ValueError, RecursionError):
        raise HttpsFailure(BAD_RESPONSE) from None
    if not isinstance(parsed, dict):
        raise HttpsFailure(BAD_RESPONSE)
    return parsed


def _answer_from_http_error(error: urllib.error.HTTPError) -> tuple[int, dict[str, object]]:
    """An error status is an answer (its JSON body when readable), except a redirect, which is refused."""
    if REDIRECT_FIRST <= error.code < REDIRECT_END:
        raise HttpsFailure(REDIRECT) from None
    try:
        return error.code, _parse_object(error.read(MAX_RESPONSE_BYTES + 1))
    except (HttpsFailure, OSError, http.client.HTTPException):  # a body cut short is no reason to lose the status
        return error.code, {}


def _network_reason(error: Exception) -> str:
    timed_out = isinstance(error, TimeoutError) or (
        isinstance(error, urllib.error.URLError) and isinstance(error.reason, TimeoutError))
    if timed_out:
        return TIMEOUT
    return BAD_RESPONSE if isinstance(error, http.client.HTTPException) else UNREACHABLE


def request_json(base_url: str, method: str, path: str, token: str | None = None,
                 body: dict[str, object] | None = None,
                 opener: urllib.request.OpenerDirector = OPENER) -> tuple[int, dict[str, object]]:
    """Send one request and return (status, JSON object); raises HttpsFailure for anything else."""
    if not base_url.startswith(HTTPS_PREFIX):
        raise HttpsFailure(INSECURE)
    request = _build_request(base_url, method, path, token, body)
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.status, _parse_object(response.read(MAX_RESPONSE_BYTES + 1))
    except urllib.error.HTTPError as error:
        return _answer_from_http_error(error)
    except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
        raise HttpsFailure(_network_reason(error)) from None
