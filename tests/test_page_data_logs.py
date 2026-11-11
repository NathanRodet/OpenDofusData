"""Headless-safe checks of the Données and Logs pages (skipped when no display is available)."""

import json
import threading
from datetime import datetime, timezone

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.capture_session import CaptureSession
from opendofusdata.categories import CATEGORIES, CATEGORY_HDV, CategorySettings
from opendofusdata.log_feed import MAX_LOG_LINES, LogFeed
from opendofusdata.page_data import DataPage
from opendofusdata.page_logs import LogsPage
from opendofusdata.records import LotPrice
from opendofusdata.window_context import WindowContext

MOMENT = datetime(2026, 11, 11, 13, 32, 5, tzinfo=timezone.utc)


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(1.0)


def make_context(tmp_path, config_path=None) -> WindowContext:
    session = CaptureSession(str(tmp_path / "p.db"), "Brial", None, idle_capture, lambda: MOMENT,
                             categories=CategorySettings([CATEGORY_HDV]), feed=LogFeed())
    return WindowContext(session, lambda: None, config_path or tmp_path / "config.json",
                         ["Brial"], lambda item_id: f"Objet {item_id}")


def lot(item_id: int) -> LotPrice:
    return LotPrice(item_id, "Brial", 10, 5868, "2026-11-11T13:32:05Z")


def test_unavailable_categories_are_disabled_and_labelled_soon(root, tmp_path) -> None:
    page = DataPage(root, make_context(tmp_path))
    for category in CATEGORIES:
        row = page.rows[category.key]
        assert (row.switch.cget("state") == "normal") is category.available
        assert ("bientôt" in row.count_label.cget("text")) is (not category.available)


def test_hdv_switch_starts_on_and_counts_records(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = DataPage(root, context)
    assert page.rows[CATEGORY_HDV].switch.get() == 1
    page.render(context.session.snapshot())
    assert page.rows[CATEGORY_HDV].count_label.cget("text") == "0 enregistrement"


def test_toggling_hdv_updates_settings_and_config_file(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = DataPage(root, context)
    page.rows[CATEGORY_HDV].switch.toggle()
    assert context.session.categories.is_enabled(CATEGORY_HDV) is False
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["enabled_categories"] == []


def test_toggle_survives_an_unwritable_config(root, tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    context = make_context(tmp_path, blocker / "config.json")
    page = DataPage(root, context)
    page.rows[CATEGORY_HDV].switch.toggle()
    assert context.session.categories.is_enabled(CATEGORY_HDV) is False
    assert "pas pu être enregistré" in page.message_label.cget("text")


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


def test_data_page_counter_follows_the_session_records(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = DataPage(root, context)
    snapshot = context.session.snapshot()
    page.render(snapshot.__class__(snapshot.status, snapshot.server, 2, 1, None, None))
    assert page.rows[CATEGORY_HDV].count_label.cget("text") == "3 enregistrements"
