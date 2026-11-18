"""The routes of the shared events: send, the other players' feed and the player's own history, per kind."""

from typing import Annotated

from fastapi import FastAPI, Query, Request
from pydantic import BaseModel

from keyserver.change_notifier import ChangeNotifier
from keyserver.event_schemas import BrokenBatch, ManualBatch, PetBatch
from keyserver.event_store import EventStore
from keyserver.schemas import MAX_BATCH_READINGS, MAX_QUERY_INTEGER

Cursor = Annotated[int, Query(ge=0, le=MAX_QUERY_INTEGER)]
PageSize = Annotated[int, Query(ge=1, le=MAX_BATCH_READINGS)]
MINE_SUFFIX = "/mine"
# path -> (kind stored in the journal, body model of the POST)
EVENT_ROUTES: dict[str, tuple[str, type[BaseModel]]] = {
    "/brisages": ("broken", BrokenBatch),
    "/familiers": ("pet", PetBatch),
    "/saisies": ("manual", ManualBatch),
}


def _register(app: FastAPI, events: EventStore, path: str, kind: str, batch_model: type[BaseModel],
              notifier: ChangeNotifier | None) -> None:
    @app.post(path)
    def send(batch: batch_model, request: Request) -> dict[str, int]:  # type: ignore[valid-type]
        accepted, duplicates = events.add_batch(kind, request.state.key_id, batch.events)  # type: ignore[attr-defined]
        if accepted and notifier is not None:
            notifier.notify(kind)
        return {"accepted": accepted, "duplicates": duplicates}

    @app.get(path)
    def changes(request: Request, since: Cursor, limit: PageSize) -> dict[str, object]:
        page = events.changes_since(kind, request.state.key_id, since, limit)
        return {"events": [event.view() for event in page], "next": page[-1].seq if page else since}

    @app.get(path + MINE_SUFFIX)
    def mine(request: Request, after: Cursor, limit: PageSize) -> dict[str, object]:
        page = events.own_page(kind, request.state.key_id, after, limit)
        return {"events": [event.view() for event in page], "next": page[-1].seq if page else after}


def register_event_routes(app: FastAPI, events: EventStore, notifier: ChangeNotifier | None = None) -> None:
    """Add `POST`, `GET` and `GET .../mine` for every kind of shared event (user keys only)."""
    for path, (kind, batch_model) in EVENT_ROUTES.items():
        _register(app, events, path, kind, batch_model, notifier)
