"""Shared helpers of the data page tests: a context over a temporary database."""

from datetime import datetime, timezone

from opendofusdata.capture_session import CaptureSession
from opendofusdata.storage import PriceStore
from opendofusdata.window_context import WindowContext

NOW = datetime(2026, 11, 12, 18, 42, tzinfo=timezone.utc)
SERVER = "Brial"


def make_context(tmp_path, names: dict[int, str] | None = None) -> WindowContext:
    names = names or {}
    session = CaptureSession(str(tmp_path / "p.db"), SERVER, None, lambda pipeline, interface, stop: stop.wait(1.0),
                             lambda: NOW)
    return WindowContext(session, tmp_path / "config.json", [SERVER, "Kourial"],
                         lambda item_id: names.get(item_id, "N/A"), type_of=lambda item_id: "Ressource")


def open_store(tmp_path) -> PriceStore:
    return PriceStore(str(tmp_path / "p.db"))
