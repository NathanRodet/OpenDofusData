"""The format a request must have to reach a route: pure rules, no web framework involved."""

from typing import NamedTuple

MAX_BODY_BYTES = 1_048_576
JSON_TYPE = "application/json"
ACCEPTED_CHARSET_PARAMETER = "charset=utf-8"
ALLOWED_ROUTES: dict[str, frozenset[str]] = {"/check": frozenset({"GET"}), "/admin/revoke": frozenset({"POST"})}


class Rejection(NamedTuple):
    """Why a request is refused: the HTTP status, a generic detail and the Allow header value if any."""

    status: int
    detail: str
    allow: str | None = None


NOT_FOUND = Rejection(404, "not_found")
UNEXPECTED_QUERY = Rejection(400, "unexpected_query")
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


def check_format(method: str, path: str, query: bytes, content_type: str | None, has_body: bool) -> Rejection | None:
    """None when the request may go on; otherwise the refusal. The path is compared exactly, never normalised."""
    methods = ALLOWED_ROUTES.get(path)
    if methods is None:
        return NOT_FOUND
    if method not in methods:
        return Rejection(405, "method_not_allowed", ", ".join(sorted(methods)))
    if query:
        return UNEXPECTED_QUERY
    if has_body and not _is_json_content_type(content_type):
        return UNSUPPORTED_MEDIA_TYPE
    return None
