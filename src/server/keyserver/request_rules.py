"""The format a request must have to reach a route: pure rules, no web framework involved."""

import re
from typing import NamedTuple

MAX_BODY_BYTES = 1_048_576
JSON_TYPE = "application/json"
ACCEPTED_CHARSET_PARAMETER = "charset=utf-8"
ALLOWED_ROUTES: dict[str, frozenset[str]] = {
    "/check": frozenset({"GET"}), "/admin/revoke": frozenset({"POST"}),
    "/readings": frozenset({"GET", "POST"}), "/readings/latest": frozenset({"GET"}),
    "/readings/mine": frozenset({"GET"}),
}
EVENT_PATHS = ("/brisages", "/familiers", "/saisies")  # the shared events: same shape as the readings routes
ALLOWED_ROUTES.update({path: frozenset({"GET", "POST"}) for path in EVENT_PATHS})
ALLOWED_ROUTES.update({f"{path}/mine": frozenset({"GET"}) for path in EVENT_PATHS})
# The only query strings that may reach a route: these parameter names, each once, as plain whole numbers.
QUERY_PARAMETERS: dict[tuple[str, str], frozenset[str]] = {
    ("/readings", "GET"): frozenset({"since", "limit"}),
    ("/readings/latest", "GET"): frozenset({"after", "limit"}),
    ("/readings/mine", "GET"): frozenset({"after", "limit"}),
}
QUERY_PARAMETERS.update({(path, "GET"): frozenset({"since", "limit"}) for path in EVENT_PATHS})
QUERY_PARAMETERS.update({(f"{path}/mine", "GET"): frozenset({"after", "limit"}) for path in EVENT_PATHS})
QUERY_PAIR = re.compile(rb"([a-z]+)=([0-9]{1,12})")
QUERY_SEPARATOR = b"&"


class Rejection(NamedTuple):
    """Why a request is refused: the HTTP status, a generic detail and the Allow header value if any."""

    status: int
    detail: str
    allow: str | None = None


NOT_FOUND = Rejection(404, "not_found")
UNEXPECTED_QUERY = Rejection(400, "unexpected_query")
UNEXPECTED_BODY = Rejection(400, "unexpected_body")
UNSUPPORTED_MEDIA_TYPE = Rejection(415, "unsupported_media_type")


def _is_json_content_type(content_type: str | None) -> bool:
    """`application/json`, alone or with `charset=utf-8` (case ignored); nothing else."""
    if not content_type:
        return False
    media_type, *parameters = [part.strip() for part in content_type.split(";")]
    if media_type.lower() != JSON_TYPE:
        return False
    if not parameters:
        return True
    return len(parameters) == 1 and parameters[0].lower().replace(" ", "") == ACCEPTED_CHARSET_PARAMETER


def _query_is_allowed(method: str, path: str, query: bytes) -> bool:
    """True for an empty query, or one made only of this route's own parameters, each once, as whole numbers."""
    if not query:
        return True
    names = []
    for part in query.split(QUERY_SEPARATOR):
        pair = QUERY_PAIR.fullmatch(part)
        if pair is None:
            return False
        names.append(pair.group(1).decode("ascii"))
    allowed = QUERY_PARAMETERS.get((path, method), frozenset())
    return len(set(names)) == len(names) and set(names) <= allowed


def check_format(method: str, path: str, query: bytes, content_type: str | None, has_body: bool) -> Rejection | None:
    """None when the request may go on; otherwise the refusal. The path is compared exactly, never normalised."""
    methods = ALLOWED_ROUTES.get(path)
    if methods is None:
        return NOT_FOUND
    if method not in methods:
        return Rejection(405, "method_not_allowed", ", ".join(sorted(methods)))
    if not _query_is_allowed(method, path, query):
        return UNEXPECTED_QUERY
    if method == "GET" and has_body:
        return UNEXPECTED_BODY
    if has_body and not _is_json_content_type(content_type):
        return UNSUPPORTED_MEDIA_TYPE
    return None
