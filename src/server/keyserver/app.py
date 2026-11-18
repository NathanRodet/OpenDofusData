"""The HTTP application: authenticated routes behind the guard middlewares."""

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from keyserver.admin_routes import register_admin_routes
from keyserver.auth import BearerAuthMiddleware, KeyVerifier
from keyserver.guards import BodyLimitMiddleware, RequestFormatMiddleware
from keyserver.change_notifier import ChangeNotifier
from keyserver.reading_routes import register_reading_routes
from keyserver.readings_store import ReadingStore, open_readings
from keyserver.request_rules import MAX_BODY_BYTES
from keyserver.retention import start_purge_loop
from keyserver.revocations import RevocationStore, open_revocations
from keyserver.settings import Settings, load_settings
from keyserver.signed_keys import admin_token
from keyserver.stream_routes import register_stream_routes

CHECK_PATH = "/check"
OK_BODY = {"status": "ok"}
INVALID_BODY = {"detail": "invalid_body"}
UNPROCESSABLE_STATUS = 422


async def refuse_invalid_body(request: Request, error: Exception) -> JSONResponse:
    """A generic 422: FastAPI's default answer would repeat the offending input."""
    return JSONResponse(INVALID_BODY, status_code=UNPROCESSABLE_STATUS)


def create_app(settings: Settings, revocations: RevocationStore, readings: ReadingStore) -> FastAPI:
    """The application; interactive docs are off (no front, nothing useless exposed)."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get(CHECK_PATH)
    def check() -> dict[str, str]:
        """Tell the player their key works."""
        return OK_BODY

    notifier = ChangeNotifier()
    register_reading_routes(app, readings, notifier)
    register_stream_routes(app, notifier)
    register_admin_routes(app, revocations, readings)
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
    readings = open_readings(settings.db_path)
    start_purge_loop(readings)
    return create_app(settings, open_revocations(settings.db_path), readings)
