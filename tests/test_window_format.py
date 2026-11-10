"""Tests for the pure French texts of the window."""

from datetime import datetime, timezone

from dofus_prices.app_links import APP_NAME, SAAS_URL
from dofus_prices.capture_session import CaptureStatus, SessionSnapshot
from dofus_prices.window_format import (
    button_label, counts_text, last_record_text, server_text, status_text,
)


def snapshot(status: CaptureStatus = CaptureStatus.RUNNING, error: str | None = None,
             last: datetime | None = None) -> SessionSnapshot:
    return SessionSnapshot(status, "Brial", 3, 2, last, error)


def test_status_texts() -> None:
    assert status_text(snapshot()) == "Capture active"
    assert status_text(snapshot(CaptureStatus.STOPPED)) == "Capture arrêtée"
    assert status_text(snapshot(CaptureStatus.ERROR, "Npcap absent")) == "Erreur : Npcap absent"
    assert status_text(snapshot(CaptureStatus.ERROR)) == "Erreur"


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
