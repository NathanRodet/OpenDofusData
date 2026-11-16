"""French texts of the capture window (pure functions, no tkinter)."""

from datetime import datetime

from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.game_servers import UNKNOWN_SERVER
from opendofusdata.time_filters import elapsed_text

NO_RECORD_TEXT = "aucun pour l'instant"
UNCHOSEN_SERVER_TEXT = "Serveur : non choisi (à régler dans Réglages)"
STATUS_TEXTS = {
    CaptureStatus.RUNNING: "Capture active",
    CaptureStatus.STOPPING: "Arrêt en cours...",
    CaptureStatus.STOPPED: "Capture arrêtée",
    CaptureStatus.ERROR: "Erreur",
}
STOP_LABEL = "Arrêter"
RESTART_LABEL = "Relancer"
STOPPING_LABEL = "Arrêt en cours..."


HEADLINE_TEXTS = {**STATUS_TEXTS, CaptureStatus.ERROR: "Erreur de capture"}


def headline_text(snapshot: SessionSnapshot) -> str:
    """The big status title of the home page (no error message)."""
    return HEADLINE_TEXTS[snapshot.status]


def error_detail_text(snapshot: SessionSnapshot) -> str:
    """The error message shown under the title, empty when there is no error."""
    if snapshot.status is CaptureStatus.ERROR and snapshot.error_message:
        return snapshot.error_message
    return ""


def total_records(snapshot: SessionSnapshot) -> int:
    """Prices plus statistics recorded during this session."""
    return snapshot.price_count + snapshot.stats_count


def counts_text(snapshot: SessionSnapshot) -> str:
    """Records saved during this session."""
    return (f"Prix enregistrés : {snapshot.price_count}\n"
            f"Statistiques enregistrées : {snapshot.stats_count}")


def button_label(snapshot: SessionSnapshot) -> str:
    """Label of the stop/restart button."""
    if snapshot.status is CaptureStatus.STOPPING:
        return STOPPING_LABEL
    return STOP_LABEL if snapshot.status is CaptureStatus.RUNNING else RESTART_LABEL


def button_enabled(snapshot: SessionSnapshot) -> bool:
    """The button is disabled while the capture is stopping."""
    return snapshot.status is not CaptureStatus.STOPPING


def status_rows(snapshot: SessionSnapshot, now: datetime) -> list[tuple[str, str]]:
    """The labelled lines of the menu status block."""
    unchosen = snapshot.server == UNKNOWN_SERVER
    last = NO_RECORD_TEXT if snapshot.last_record_at is None else elapsed_text(snapshot.last_record_at, now)
    return [("Serveur", "non choisi" if unchosen else snapshot.server),
            ("Prix", str(total_records(snapshot))),
            ("Brisages", str(snapshot.breaking_count)),
            ("Familiers", str(snapshot.pet_count)),
            ("Dernier relevé", last)]
