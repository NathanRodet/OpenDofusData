"""French texts of the capture window (pure functions, no tkinter)."""

from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.log_feed import TIME_FORMAT

NO_RECORD_TEXT = "aucun pour l'instant"
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


def records_text(count: int) -> str:
    """'0 enregistrement', '1 enregistrement', '2 enregistrements' (French plural)."""
    return f"{count} enregistrement" + ("s" if count > 1 else "")


def total_records(snapshot: SessionSnapshot) -> int:
    """Prices plus statistics recorded during this session."""
    return snapshot.price_count + snapshot.stats_count


def server_text(snapshot: SessionSnapshot) -> str:
    """Server line."""
    return f"Serveur : {snapshot.server}"


def counts_text(snapshot: SessionSnapshot) -> str:
    """Records saved during this session."""
    return (f"Prix enregistrés : {snapshot.price_count}\n"
            f"Statistiques enregistrées : {snapshot.stats_count}")


def last_record_text(snapshot: SessionSnapshot) -> str:
    """Local time of the last record, or a placeholder."""
    moment = snapshot.last_record_at
    shown = NO_RECORD_TEXT if moment is None else moment.astimezone().strftime(TIME_FORMAT)
    return f"Dernier enregistrement : {shown}"


def button_label(snapshot: SessionSnapshot) -> str:
    """Label of the stop/restart button."""
    if snapshot.status is CaptureStatus.STOPPING:
        return STOPPING_LABEL
    return STOP_LABEL if snapshot.status is CaptureStatus.RUNNING else RESTART_LABEL


def button_enabled(snapshot: SessionSnapshot) -> bool:
    """The button is disabled while the capture is stopping."""
    return snapshot.status is not CaptureStatus.STOPPING
