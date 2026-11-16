"""The reading routes: send prices (POST), then fetch what the other players sent (GET)."""

from typing import Annotated

from fastapi import FastAPI, Query, Request

from keyserver.event_routes import register_event_routes
from keyserver.readings_store import ReadingStore, StoredReading
from keyserver.schemas import MAX_BATCH_READINGS, MAX_QUERY_INTEGER, ReadingBatch

READINGS_PATH = "/readings"
LATEST_PATH = "/readings/latest"
MINE_PATH = "/readings/mine"
Cursor = Annotated[int, Query(ge=0, le=MAX_QUERY_INTEGER)]
PageSize = Annotated[int, Query(ge=1, le=MAX_BATCH_READINGS)]


def _view(readings: list[StoredReading]) -> list[dict[str, object]]:
    """The readings as sent to the players: the sender's key id is a pseudonym, never the key itself."""
    return [reading._asdict() for reading in readings]


def register_reading_routes(app: FastAPI, readings: ReadingStore) -> None:
    """Add `POST /readings`, `GET /readings` and `GET /readings/latest` and `GET /readings/mine` (user keys only)."""

    register_event_routes(app, readings.events)

    @app.post(READINGS_PATH)
    def send(batch: ReadingBatch, request: Request) -> dict[str, int]:
        accepted, duplicates = readings.add_batch(request.state.key_id, batch.readings)
        return {"accepted": accepted, "duplicates": duplicates}

    @app.get(READINGS_PATH)
    def changes(request: Request, since: Cursor, limit: PageSize) -> dict[str, object]:
        page = readings.changes_since(request.state.key_id, since, limit)
        return {"readings": _view(page), "next": page[-1].seq if page else since}

    @app.get(LATEST_PATH)
    def latest(request: Request, after: Cursor, limit: PageSize) -> dict[str, object]:
        as_of = readings.highest_seq()  # read first: a reading that lands during the page query is fetched later
        page = readings.latest_page(request.state.key_id, after, limit)
        return {"readings": _view(page), "next": page[-1].seq if page else after,
                "as_of": as_of, "done": len(page) < limit}

    @app.get(MINE_PATH)
    def mine(request: Request, after: Cursor, limit: PageSize) -> dict[str, object]:
        page = readings.own_page(request.state.key_id, after, limit)
        return {"readings": _view(page), "next": page[-1].seq if page else after}
