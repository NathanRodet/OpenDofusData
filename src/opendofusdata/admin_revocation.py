"""What the Administration tab says and asks when revoking a key (with or without deleting its readings)."""

from collections.abc import Callable
from tkinter import messagebox

from opendofusdata.admin_client import RevokeResult

REVOKING_TEXT = "Révocation en cours..."
BUSY_TEXT = "Une révocation est déjà en cours, attends qu'elle se termine."
CONFIRM_TITLE = "Révoquer la clé"
CONFIRM_TEXT = "Révoquer la clé de {label} ? Elle sera refusée par le serveur immédiatement."
CONFIRM_PURGE_TEXT = ("Révoquer la clé de {label} et supprimer ses relevés du serveur ? Elle sera refusée "
                      "immédiatement; les prix déjà récupérés par les autres joueurs restent chez eux.")
Revoke = Callable[..., RevokeResult]
Confirm = Callable[[str], bool]


class RevokeFailed(Exception):
    """The server did not revoke the key; the message is what the administrator reads."""


def ask_confirmation(text: str) -> bool:
    """Ask yes or no in a system dialog."""
    return bool(messagebox.askyesno(CONFIRM_TITLE, text))
