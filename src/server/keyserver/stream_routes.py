"""`GET /stream`: a long answer that only says "something changed" (the data itself comes from the usual routes)."""

import asyncio
import json
import time
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from keyserver.change_notifier import ChangeNotifier, changed_kinds

STREAM_PATH = "/stream"
CHECK_SECONDS = 0.5  # how often the counters are compared (an in-memory read)
HEARTBEAT_SECONDS = 10.0  # shorter than the proxy's read timeout, so a quiet stream is never cut
MAX_STREAM_SECONDS = 600.0  # the player reconnects: a stale connection never lives for ever
TOO_MANY_STREAMS = {"detail": "stream_already_open"}
TOO_MANY_STATUS = 429
STREAM_HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
READY_FRAME = "retry: 5000\nevent: ready\ndata: {}\n\n"
HEARTBEAT_FRAME = ": keepalive\n\n"


def changed_frame(kinds: list[str]) -> str:
    """One server-sent event that names the kinds of data that changed."""
    return f"event: changed\ndata: {json.dumps(kinds)}\n\n"


async def _frames(request: Request, notifier: ChangeNotifier, key_id: str) -> AsyncIterator[str]:
    try:
        yield READY_FRAME
        seen, started, last_sent = notifier.snapshot(), time.monotonic(), time.monotonic()
        while time.monotonic() - started < MAX_STREAM_SECONDS and not await request.is_disconnected():
            await asyncio.sleep(CHECK_SECONDS)
            now, kinds = time.monotonic(), changed_kinds(seen, notifier.snapshot())
            if kinds:
                seen, last_sent = notifier.snapshot(), now
                yield changed_frame(kinds)
            elif now - last_sent >= HEARTBEAT_SECONDS:
                last_sent = now
                yield HEARTBEAT_FRAME
    finally:
        notifier.close_slot(key_id)


def register_stream_routes(app: FastAPI, notifier: ChangeNotifier) -> None:
    """Add `GET /stream` (user keys only; one open stream per key)."""

    @app.get(STREAM_PATH, response_model=None)
    async def stream(request: Request) -> StreamingResponse | JSONResponse:
        key_id = request.state.key_id
        if not notifier.open_slot(key_id):
            return JSONResponse(TOO_MANY_STREAMS, status_code=TOO_MANY_STATUS)
        return StreamingResponse(_frames(request, notifier, key_id), media_type="text/event-stream",
                                 headers=STREAM_HEADERS)
