"""The HTTP application: authenticated routes behind the guard middlewares."""

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from keyserver.admin_routes import register_admin_routes
from keyserver.auth import BearerAuthMiddleware, KeyVerifier
from keyserver.guards import BodyLimitMiddleware, RequestFormatMiddleware
from keyserver.request_rules import MAX_BODY_BYTES
from keyserver.revocations import RevocationStore, open_revocations
from keyserver.settings import Settings, load_settings
from keyserver.signed_keys import admin_token

CHECK_PATH = "/check"
OK_BODY = {"status": "ok"}
INVALID_BODY = {"detail": "invalid_body"}
UNPROCESSABLE_STATUS = 422


async def refuse_invalid_body(request: Request, error: Exception) -> JSONResponse:
    """A generic 422: FastAPI's default answer would repeat the offending input."""
    return JSONResponse(INVALID_BODY, status_code=UNPROCESSABLE_STATUS)


def create_app(settings: Settings, revocations: RevocationStore) -> FastAPI:
    """The application; interactive docs are off (no front, nothing useless exposed)."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get(CHECK_PATH)
    def check() -> dict[str, str]:
        """Tell the player their key works."""
        return OK_BODY

    register_admin_routes(app, revocations)
    app.add_exception_handler(RequestValidationError, refuse_invalid_body)
    # The last middleware added is the outermost: Host check, size limit, then authentication, then request format.
    app.add_middleware(RequestFormatMiddleware)
    app.add_middleware(BearerAuthMiddleware, verifier=KeyVerifier(settings.key_secret, revocations),
                       admin_token_value=admin_token(settings.key_secret))
    app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    return app


def build_app() -> FastAPI:
    """The application configured from the environment (used with `uvicorn --factory`)."""
    settings = load_settings(os.environ)
    return create_app(settings, open_revocations(settings.db_path))
