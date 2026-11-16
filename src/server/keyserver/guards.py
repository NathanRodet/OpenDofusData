"""ASGI guards run before any route: the body size limit and the strict request format."""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from keyserver.request_rules import MAX_BODY_BYTES, Rejection, check_format

HEADER_ENCODING = "latin-1"
BODY_TOO_LARGE = Rejection(413, "payload_too_large")
BAD_REQUEST = Rejection(400, "bad_request")
MAX_LENGTH_DIGITS = 12  # far above any accepted body: a longer number is refused before int() sees it


class BodyTooLarge(Exception):
    """Raised inside the receive channel when the streamed body goes over the limit."""


class InvalidContentLength(Exception):
    """The Content-Length header is repeated or is not a whole number."""


async def respond(send: Send, rejection: Rejection) -> None:
    """Send a generic JSON refusal; nothing of the request is echoed back."""
    body = json.dumps({"detail": rejection.detail}).encode("utf-8")
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode("ascii"))]
    if rejection.allow:
        headers.append((b"allow", rejection.allow.encode("ascii")))
    await send({"type": "http.response.start", "status": rejection.status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def header_values(scope: Scope, name: bytes) -> list[str]:
    """Every value the request carries for this (lowercase) header name."""
    return [value.decode(HEADER_ENCODING) for key, value in scope["headers"] if key == name]


def declared_length(scope: Scope) -> int | None:
    """The Content-Length as a number, None when absent; InvalidContentLength when repeated or not a number."""
    values = header_values(scope, b"content-length")
    if not values:
        return None
    if len(values) > 1 or not values[0].isascii() or not values[0].isdigit() or len(values[0]) > MAX_LENGTH_DIGITS:
        raise InvalidContentLength
    return int(values[0])


def has_body(scope: Scope) -> bool:
    """True when the request announces a body (positive length or chunked transfer)."""
    return bool(header_values(scope, b"transfer-encoding")) or (declared_length(scope) or 0) > 0


class CountingReceive:
    """The receive channel, raising BodyTooLarge as soon as the streamed bytes exceed the limit."""

    def __init__(self, receive: Receive, max_bytes: int) -> None:
        self._receive, self._max_bytes, self._received = receive, max_bytes, 0
        self.exceeded = False

    async def __call__(self) -> Message:
        message = await self._receive()
        self._received += len(message.get("body", b""))
        if self._received > self._max_bytes:
            self.exceeded = True
            raise BodyTooLarge
        return message


class BodyLimitMiddleware:
    """Refuses a body over the limit: from its declared length, or as soon as the streamed bytes exceed it."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        try:
            declared = declared_length(scope)
        except InvalidContentLength:
            await respond(send, BAD_REQUEST)
            return
        if declared is not None and declared > self._max_bytes:
            await respond(send, BODY_TOO_LARGE)
            return
        await self._run_counting(scope, receive, send)

    async def _run_counting(self, scope: Scope, receive: Receive, send: Send) -> None:
        counting = CountingReceive(receive, self._max_bytes)
        started = False

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if counting.exceeded:  # the framework may turn our exception into its own error: drop its answer
                return
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self._app(scope, counting, guarded_send)
        except BodyTooLarge:
            pass
        if counting.exceeded and not started:
            await respond(send, BODY_TOO_LARGE)


def request_path(scope: Scope) -> str:
    """The path as the client sent it (not percent-decoded), so `/check%2F` never equals `/check/`."""
    raw = scope.get("raw_path")
    return raw.decode(HEADER_ENCODING) if raw else scope["path"]


class RequestFormatMiddleware:
    """Lets through only the exact routes, methods, queries and content types the application expects."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        content_types = header_values(scope, b"content-type")
        content_type = content_types[0] if len(content_types) == 1 else None
        rejection = check_format(scope["method"], request_path(scope), scope["query_string"], content_type,
                                 has_body(scope))
        if rejection is None:
            await self._app(scope, receive, send)
        else:
            await respond(send, rejection)
