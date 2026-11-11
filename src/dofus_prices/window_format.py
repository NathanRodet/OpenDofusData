"""French texts of the capture window (pure functions, no tkinter)."""

from dofus_prices.capture_session import CaptureStatus, SessionSnapshot

NO_RECORD_TEXT = "aucun pour l'instant"
TIME_FORMAT = "%H:%M:%S"
STATUS_TEXTS = {
    CaptureStatus.RUNNING: "Capture active",
    CaptureStatus.STOPPING: "Arrêt en cours...",
    CaptureStatus.STOPPED: "Capture arrêtée",
    CaptureStatus.ERROR: "Erreur",
}
STOP_LABEL = "Arrêter"
RESTART_LABEL = "Relancer"
STOPPING_LABEL = "Arrêt en cours..."


def status_text(snapshot: SessionSnapshot) -> str:
    """Status line; an error is followed by its French message."""
    text = STATUS_TEXTS[snapshot.status]
    if snapshot.status is CaptureStatus.ERROR and snapshot.error_message:
        return f"{text} : {snapshot.error_message}"
    return text


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
