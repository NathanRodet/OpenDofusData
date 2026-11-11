"""Tests for the pure French texts of the window."""

from datetime import datetime, timezone

from opendofusdata.app_links import APP_NAME, SAAS_URL
from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.window_format import (
    button_enabled, button_label, counts_text, error_detail_text, headline_text, last_record_text,
    records_text, server_text, total_records,
)


def snapshot(status: CaptureStatus = CaptureStatus.RUNNING, error: str | None = None,
             last: datetime | None = None) -> SessionSnapshot:
    return SessionSnapshot(status, "Brial", 3, 2, last, error)


def test_headline_texts() -> None:
    assert headline_text(snapshot(CaptureStatus.STOPPED)) == "Capture arrêtée"
    assert headline_text(snapshot(CaptureStatus.STOPPING)) == "Arrêt en cours..."


def test_server_and_counts() -> None:
    assert server_text(snapshot()) == "Serveur : Brial"
    assert "Prix enregistrés : 3" in counts_text(snapshot())
    assert "Statistiques enregistrées : 2" in counts_text(snapshot())


def test_last_record_text() -> None:
    assert "aucun" in last_record_text(snapshot())
    moment = datetime(2026, 11, 11, 12, 30, 45, tzinfo=timezone.utc)
    assert last_record_text(snapshot(last=moment)) == (
        "Dernier enregistrement : " + moment.astimezone().strftime("%H:%M:%S"))


def test_button_label_follows_status() -> None:
    assert button_label(snapshot()) == "Arrêter"
    assert button_label(snapshot(CaptureStatus.STOPPED)) == "Relancer"
    assert button_label(snapshot(CaptureStatus.ERROR)) == "Relancer"


def test_product_constants() -> None:
    assert APP_NAME == "OpenDofusData" and SAAS_URL.startswith("https://")


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


def test_records_text_uses_the_french_plural() -> None:
    assert [records_text(count) for count in (0, 1, 2, 20)] == [
        "0 enregistrement", "1 enregistrement", "2 enregistrements", "20 enregistrements"]


def test_total_records_adds_prices_and_stats() -> None:
    assert total_records(snapshot()) == 5
