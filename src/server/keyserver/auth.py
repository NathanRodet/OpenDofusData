"""Bearer authentication (RFC 6750): one uniform 401 whatever is wrong with the key."""

import hmac
import json

from starlette.types import ASGIApp, Receive, Scope, Send

from keyserver.guards import request_path
from keyserver.revocations import RevocationStore
from keyserver.signed_keys import parse_key, signature_is_valid

BEARER_SCHEME = "bearer"
ADMIN_PREFIX = "/admin"
TOKEN_ENCODING = "utf-8"
AUTHORIZATION_HEADER = b"authorization"
HEADER_ENCODING = "latin-1"
UNAUTHORIZED_STATUS = 401
UNAUTHORIZED_BODY = json.dumps({"detail": "unauthorized"}).encode("utf-8")
WEBSOCKET_POLICY_CLOSE = 1008
UNAUTHORIZED_HEADERS = [
    (b"content-type", b"application/json"),
    (b"content-length", str(len(UNAUTHORIZED_BODY)).encode("ascii")),
    (b"www-authenticate", b"Bearer"),
]


def bearer_token(header: str | None) -> str | None:
    """The token of a strict `Bearer <token>` header (scheme case-insensitive), else None."""
    if not header:
        return None
    parts = header.split(" ")
    if len(parts) != 2 or parts[0].lower() != BEARER_SCHEME or not parts[1]:
        return None
    return parts[1]


class KeyVerifier:
    """A key is valid when it is signed with the secret and its identifier is not revoked."""

    def __init__(self, secret: str, revocations: RevocationStore) -> None:
        self._secret = secret
        self._revocations = revocations

    def is_valid(self, key: str) -> bool:
        """True for a correctly signed, non-revoked key."""
        key_id = parse_key(key)
        if key_id is None or not signature_is_valid(self._secret, key):
            return False
        return not self._revocations.is_revoked(key_id)


def is_admin_path(path: str) -> bool:
    """True for `/admin` and everything under `/admin/` (exact, case-sensitive: no look-alike counts)."""
    return path == ADMIN_PREFIX or path.startswith(ADMIN_PREFIX + "/")


def _authorization_value(scope: Scope) -> str | None:
    """The single Authorization header of the request; several of them make it ambiguous, so None."""
    values = [value for name, value in scope["headers"] if name == AUTHORIZATION_HEADER]
    return values[0].decode(HEADER_ENCODING) if len(values) == 1 else None


class BearerAuthMiddleware:
    """Two domains: `/admin/` accepts only the admin token, every other path only a valid key.

    Nothing the client sends is ever logged or echoed. Without an admin token the admin domain stays closed.
    """

    def __init__(self, app: ASGIApp, verifier: KeyVerifier, admin_token_value: str | None = None) -> None:
        self._app = app
        self._verifier = verifier
        self._admin_token = admin_token_value

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._app(scope, receive, send)
        elif scope["type"] == "http" and self._is_authorised(scope):
            await self._app(scope, receive, send)
        elif scope["type"] == "http":
            await self._reject(send)
        else:
            await send({"type": "websocket.close", "code": WEBSOCKET_POLICY_CLOSE})

    def _is_authorised(self, scope: Scope) -> bool:
        token = bearer_token(_authorization_value(scope))
        if token is None:
            return False
        if is_admin_path(request_path(scope)):
            return self._is_admin_token(token)
        return self._verifier.is_valid(token)

    def _is_admin_token(self, token: str) -> bool:
        if not self._admin_token:
            return False
        return hmac.compare_digest(token.encode(TOKEN_ENCODING), self._admin_token.encode(TOKEN_ENCODING))

    @staticmethod
    async def _reject(send: Send) -> None:
        await send({"type": "http.response.start", "status": UNAUTHORIZED_STATUS, "headers": UNAUTHORIZED_HEADERS})
        await send({"type": "http.response.body", "body": UNAUTHORIZED_BODY})
