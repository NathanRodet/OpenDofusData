"""The "Mises à jour" and "À propos" cards of the Réglages page."""

import webbrowser
from collections.abc import Callable

import customtkinter

from opendofusdata import __version__
from opendofusdata.app_links import REPOSITORY_URL
from opendofusdata.background import TaskState
from opendofusdata.settings_rows import make_row
from opendofusdata.ui_theme import (
    ACCENT_COLOR, COMPACT_BUTTON_HEIGHT, COMPACT_BUTTON_WIDTH, ERROR_COLOR, MUTED_COLOR, ROW_WRAP, TINY_PADDING,
)
from opendofusdata.ui_widgets import make_button, make_label
from opendofusdata.updates import is_allowed_url
from opendofusdata.window_context import WindowContext

UPDATES_TITLE = "Mises à jour"
ABOUT_TITLE = "À propos"
SUMMARY = (
    "Outil qui lit passivement le trafic réseau de Dofus 3 et range ce qu'il voit dans une base locale.\n"
    "Données collectées : prix HDV, brisage, familiers.\n"
    "Envoi de données : seulement si tu enregistres une clé de synchronisation (carte Synchronisation): "
    "tes prix de l'HDV sont alors envoyés au serveur et ceux des autres joueurs récupérés; retire la clé pour "
    "arrêter. Sans clé, rien ne quitte ta machine, sauf la vérification des mises à jour (une requête anonyme à "
    "GitHub, désactivable) et le test de connexion, seulement quand tu cliques dessus (il n'envoie que ta clé).\n"
    "Licence : tous droits réservés (code source public)."
)
REPOSITORY_LABEL = "Voir le dépôt"
ACTION_BUTTON_WIDTH = 200  # "Mettre à jour et relancer" needs more room than the other buttons
ABOUT_WRAP = 680
CHECK_LABEL = "Rechercher les mises à jour"
CHECKING_LABEL = "Vérification..."
INSTALL_LABEL = "Mettre à jour et relancer"
INSTALLING_LABEL = "Mise à jour en cours..."
SEE_LABEL = "Voir la version"
AVAILABLE_TEXT = "● Mise à jour disponible : {version}"
CHECK_FAILED_TEXT = "Vérification impossible : {message}"
DOWNLOADING_TEXT = "Téléchargement de la mise à jour..."


def open_url(url: str) -> None:
    """Open a GitHub page in the default browser (any other address is refused)."""
    if is_allowed_url(url):
        webbrowser.open(url)


class UpdatesCard:
    """Version, update announcement and its action (never updates by itself)."""

    def __init__(self, parent: customtkinter.CTkFrame, context: WindowContext,
                 open_page: Callable[[str], None] = open_url) -> None:
        self._context, self._open_page = context, open_page
        row = make_row(parent, UPDATES_TITLE)
        self.version_label = make_label(row.body, f"Version {__version__}", color=MUTED_COLOR, anchor="w")
        self.version_label.pack(fill="x")
        self.update_label = make_label(row.body, "", anchor="w", justify="left", wraplength=ROW_WRAP)
        self.update_label.pack(fill="x", pady=TINY_PADDING)
        self.action_button = make_button(row.controls, CHECK_LABEL, self._on_action, ACTION_BUTTON_WIDTH,
                                         COMPACT_BUTTON_HEIGHT)
        self.action_button.pack()

    def _status(self) -> tuple[str, str]:
        updates = self._context.updates
        install, check, info = updates.install_snapshot(), updates.check_snapshot(), updates.available()
        if install.state is TaskState.RUNNING:
            return DOWNLOADING_TEXT, MUTED_COLOR
        if install.state is TaskState.DONE:
            return install.message, MUTED_COLOR
        if install.state is TaskState.FAILED:
            return install.message, ERROR_COLOR
        if info is not None:
            return AVAILABLE_TEXT.format(version=info.version), ACCENT_COLOR
        if check.state is TaskState.FAILED:
            return CHECK_FAILED_TEXT.format(message=check.message), ERROR_COLOR
        return check.message, MUTED_COLOR

    def _button(self) -> tuple[str, bool]:
        updates = self._context.updates
        info, installing = updates.available(), updates.install_snapshot().state
        if installing in (TaskState.RUNNING, TaskState.DONE):
            return INSTALLING_LABEL, False
        if info is not None:
            return (INSTALL_LABEL if info.can_install and updates.can_self_update else SEE_LABEL), True
        checking = updates.check_snapshot().state is TaskState.RUNNING
        return (CHECKING_LABEL if checking else CHECK_LABEL), not checking

    def _on_action(self) -> None:
        updates = self._context.updates
        info = updates.available()
        if info is None:
            updates.start_check(manual=True)
        elif not updates.start_install():
            self._open_page(info.page_url)

    def render(self) -> None:
        """Show the update state and the matching action."""
        text, color = self._status()
        self.update_label.configure(text=text, text_color=color)
        label, enabled = self._button()
        self.action_button.configure(text=label, state="normal" if enabled else "disabled")


class AboutCard:
    """What the tool collects and sends, and the link to the repository."""

    def __init__(self, parent: customtkinter.CTkFrame, open_page: Callable[[str], None] = open_url) -> None:
        row = make_row(parent, ABOUT_TITLE)
        self.summary_label = make_label(row.body, SUMMARY, color=MUTED_COLOR, anchor="w", justify="left",
                                        wraplength=ABOUT_WRAP)
        self.summary_label.pack(fill="x")
        make_button(row.controls, REPOSITORY_LABEL, lambda: open_page(REPOSITORY_URL), COMPACT_BUTTON_WIDTH,
                    COMPACT_BUTTON_HEIGHT).pack()
