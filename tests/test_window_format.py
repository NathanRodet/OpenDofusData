"""Tests for the pure French texts of the window."""

from datetime import datetime

from opendofusdata.app_links import APP_NAME
from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.window_format import (
    button_enabled, button_label, error_detail_text, headline_text, total_records,
)


def snapshot(status: CaptureStatus = CaptureStatus.RUNNING, error: str | None = None,
             last: datetime | None = None) -> SessionSnapshot:
    return SessionSnapshot(status, "Brial", 3, 2, last, error)


def test_headline_texts() -> None:
    assert headline_text(snapshot(CaptureStatus.STOPPED)) == "Capture arrêtée"
    assert headline_text(snapshot(CaptureStatus.STOPPING)) == "Arrêt en cours..."


def test_button_label_follows_status() -> None:
    assert button_label(snapshot()) == "Arrêter"
    assert button_label(snapshot(CaptureStatus.STOPPED)) == "Relancer"
    assert button_label(snapshot(CaptureStatus.ERROR)) == "Relancer"


def test_product_constants() -> None:
    assert APP_NAME == "OpenDofusData"


def test_stopping_state_texts_and_disabled_button() -> None:
    stopping = snapshot(CaptureStatus.STOPPING)
    assert headline_text(stopping) == "Arrêt en cours..."
    assert button_label(stopping) == "Arrêt en cours..."
    assert not button_enabled(stopping)
    assert button_enabled(snapshot())


def test_headline_is_the_status_without_the_error_message() -> None:
    assert headline_text(snapshot(CaptureStatus.ERROR, "Npcap absent")) == "Erreur de capture"
    assert headline_text(snapshot()) == "Capture active"


def test_error_detail_only_when_in_error() -> None:
    assert error_detail_text(snapshot(CaptureStatus.ERROR, "Npcap absent")) == "Npcap absent"
    assert error_detail_text(snapshot(CaptureStatus.ERROR)) == ""
    assert error_detail_text(snapshot()) == ""


def test_total_records_adds_prices_and_stats() -> None:
    assert total_records(snapshot()) == 5

