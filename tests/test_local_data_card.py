"""The "Données locales" card: the automatic purge box and the purge now button."""

import json
import threading
from datetime import datetime, timezone

import pytest

pytest.importorskip("customtkinter")

import customtkinter

from opendofusdata.capture_session import CaptureSession
from opendofusdata.local_data_card import LocalDataCard
from opendofusdata.local_purge import PurgeResult
from opendofusdata.window_context import WindowContext

MOMENT = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(2.0)


def make_context(tmp_path) -> WindowContext:
    session = CaptureSession(str(tmp_path / "old.db"), "Brial", None, idle_capture, lambda: MOMENT)
    return WindowContext(session, tmp_path / "config.json", ["Brial"], lambda item_id: "N/A")


class FakePurge:
    def __init__(self, result: PurgeResult = PurgeResult(4, 2)) -> None:
        self.result, self.calls = result, []

    def __call__(self, database_path: str) -> PurgeResult:
        self.calls.append(database_path)
        return self.result


def make_card(root, tmp_path, purge=None, confirm=lambda text: True) -> LocalDataCard:
    return LocalDataCard(customtkinter.CTkFrame(root), make_context(tmp_path), purge or FakePurge(), confirm)


def saved(tmp_path) -> dict:
    return json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))


def purge_and_wait(card: LocalDataCard) -> None:
    card.purge_now()
    assert card.task.wait(5)
    card.render()


def test_card_has_an_unchecked_automatic_box_and_a_purge_button(root, tmp_path) -> None:
    card = make_card(root, tmp_path)
    assert card.auto_box.get() == 0
    assert card.purge_button.cget("state") == "normal"


def test_the_saved_setting_is_shown(root, tmp_path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"purge_old_data": True}), encoding="utf-8")
    assert make_card(root, tmp_path).auto_box.get() == 1


def test_ticking_the_box_saves_the_setting_and_keeps_the_other_settings(root, tmp_path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"server": "Brial"}), encoding="utf-8")
    card = make_card(root, tmp_path)
    card.auto_box.select()
    card.toggle_auto()
    assert saved(tmp_path)["purge_old_data"] is True and saved(tmp_path)["server"] == "Brial"
    card.auto_box.deselect()
    card.toggle_auto()
    assert saved(tmp_path)["purge_old_data"] is False


def test_purge_button_asks_for_confirmation_and_cancel_deletes_nothing(root, tmp_path) -> None:
    texts: list[str] = []
    purge = FakePurge()
    card = make_card(root, tmp_path, purge, confirm=lambda text: texts.append(text) or False)
    card.purge_now()
    assert purge.calls == [] and len(texts) == 1
    assert "14 jours" in texts[0] and "favoris" in texts[0].lower()


def test_purge_button_runs_in_the_background_and_shows_the_count(root, tmp_path) -> None:
    purge = FakePurge(PurgeResult(4, 2))
    card = make_card(root, tmp_path, purge)
    purge_and_wait(card)
    assert purge.calls == [str(tmp_path / "old.db")]
    text = card.status_label.cget("text")
    assert "6" in text and "supprim" in text.lower()


def test_a_purge_that_deleted_nothing_says_so(root, tmp_path) -> None:
    card = make_card(root, tmp_path, FakePurge(PurgeResult(0, 0)))
    purge_and_wait(card)
    assert "rien" in card.status_label.cget("text").lower()


def test_a_database_error_is_reported_with_its_message(root, tmp_path) -> None:
    import sqlite3

    def locked(path: str) -> PurgeResult:
        raise sqlite3.OperationalError("database is locked")

    card = make_card(root, tmp_path, locked)
    purge_and_wait(card)
    assert "database is locked" in card.status_label.cget("text")


def test_a_programming_error_is_not_dressed_up_as_a_purge_failure(root, tmp_path) -> None:
    def broken(path: str) -> PurgeResult:
        raise ValueError("bug")

    card = make_card(root, tmp_path, broken)
    purge_and_wait(card)
    assert "bug" not in card.status_label.cget("text")
    assert "inattendue" in card.status_label.cget("text")
