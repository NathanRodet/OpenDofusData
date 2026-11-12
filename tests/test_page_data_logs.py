"""Headless-safe checks of the Logs page (skipped when no display is available)."""

import threading
from datetime import datetime, timezone

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.capture_session import CaptureSession
from opendofusdata.log_feed import MAX_LOG_LINES, LogFeed
from opendofusdata.page_logs import LogsPage
from opendofusdata.records import LotPrice
from opendofusdata.window_context import WindowContext

MOMENT = datetime(2026, 11, 11, 13, 32, 5, tzinfo=timezone.utc)


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(1.0)


def make_context(tmp_path, config_path=None) -> WindowContext:
    session = CaptureSession(str(tmp_path / "p.db"), "Brial", None, idle_capture, lambda: MOMENT,
                             feed=LogFeed())
    return WindowContext(session, lambda: None, config_path or tmp_path / "config.json",
                         ["Brial"], lambda item_id: f"Objet {item_id}")


def lot(item_id: int) -> LotPrice:
    return LotPrice(item_id, "Brial", 10, 5868, "2026-11-11T13:32:05Z")


def test_logs_are_hidden_by_default_and_the_switch_controls_the_feed(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = LogsPage(root, context)
    assert page.switch.get() == 0 and context.session.feed.is_visible() is False
    page.switch.toggle()
    assert context.session.feed.is_visible() is True
    page.switch.toggle()
    assert context.session.feed.is_visible() is False


def test_log_text_shows_columns_and_item_names(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = LogsPage(root, context)
    page.switch.toggle()
    context.session.feed.add(lot(307), MOMENT)
    page.render(context.session.snapshot())
    text = page.log_text()
    assert "Objet 307" in text and "lot ×10" in text and text.rstrip().endswith("5 868")


def test_log_text_shows_at_most_200_rows(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = LogsPage(root, context)
    page.switch.toggle()
    for item_id in range(MAX_LOG_LINES + 50):
        context.session.feed.add(lot(item_id), MOMENT)
    page.render(context.session.snapshot())
    assert len(page.log_text().strip().splitlines()) == MAX_LOG_LINES


def test_hidden_logs_show_a_hint_instead_of_rows(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = LogsPage(root, context)
    page.render(context.session.snapshot())
    assert "masqués" in page.hint_label.cget("text") and page.log_text() == ""


def test_hidden_logs_pack_the_hint_and_not_the_table(root, tmp_path) -> None:
    page = LogsPage(root, make_context(tmp_path))
    assert page.hint_label.winfo_manager() == "pack"
    assert page.text_box.winfo_manager() == ""
    page.switch.toggle()
    assert page.hint_label.winfo_manager() == ""
    assert page.text_box.winfo_manager() == "pack"


def test_toggling_the_logs_off_and_on_shows_no_stale_rows(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = LogsPage(root, context)
    page.switch.toggle()
    context.session.feed.add(lot(307), MOMENT)
    page.render(context.session.snapshot())
    page.switch.toggle()
    page.switch.toggle()
    page.render(context.session.snapshot())
    assert page.log_text() == ""


def test_logs_refresh_when_the_name_lookup_changes(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = LogsPage(root, context)
    page.switch.toggle()
    context.session.feed.add(lot(307), MOMENT)
    page.render(context.session.snapshot())
    context.name_of = lambda item_id: "Nouveau nom"
    page.render(context.session.snapshot())
    assert "Nouveau nom" in page.log_text()


