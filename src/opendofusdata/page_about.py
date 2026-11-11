"""The À propos page: version, update card, what the tool collects, link to the repository."""

from collections.abc import Callable

import customtkinter

from opendofusdata import __version__
from opendofusdata.app_links import REPOSITORY_URL
from opendofusdata.background import TaskState
from opendofusdata.capture_session import SessionSnapshot
from opendofusdata.ui_theme import ACCENT_COLOR, ERROR_COLOR, MUTED_COLOR, PADDING, WRAP_LENGTH
from opendofusdata.ui_widgets import add_title, make_button, make_card, make_label, make_page
from opendofusdata.window_context import WindowContext

TITLE = "À propos"
SUMMARY = (
    "Outil libre et open source qui lit passivement le trafic réseau de Dofus 3.\n"
    "Catégories collectées : HDV (recyclage, brisage et expérience des pets arrivent bientôt).\n"
    "Rien n'est envoyé hors de ta machine, sauf la vérification des mises à jour "
    "(une requête anonyme à GitHub, désactivable dans les réglages)."
)
REPOSITORY_LABEL = "Voir le dépôt"
CHECK_LABEL = "Rechercher les mises à jour"
CHECKING_LABEL = "Vérification..."
INSTALL_LABEL = "Mettre à jour et relancer"
INSTALLING_LABEL = "Mise à jour en cours..."
SEE_LABEL = "Voir la version"
AVAILABLE_TEXT = "● Mise à jour disponible : {version}"
CHECK_FAILED_TEXT = "Vérification impossible : {message}"
DOWNLOADING_TEXT = "Téléchargement de la mise à jour..."


class AboutPage:
    """Static information plus the update card (never updates by itself)."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext,
                 open_url: Callable[[str], None]) -> None:
        self._context, self._open_url = context, open_url
        self.frame, body = make_page(parent)
        add_title(body, TITLE)
        self.version_label = make_label(body, f"Version {__version__}", color=MUTED_COLOR, anchor="w")
        self.version_label.pack(fill="x", pady=(0, PADDING))
        update_card = make_card(body)
        self.update_label = make_label(update_card, "", anchor="w", justify="left", wraplength=WRAP_LENGTH)
        self.update_label.pack(fill="x", padx=PADDING, pady=(PADDING, 0))
        self.action_button = make_button(update_card, CHECK_LABEL, self._on_action)
        self.action_button.pack(pady=PADDING)
        summary_card = make_card(body)
        self.summary_label = make_label(summary_card, SUMMARY, anchor="w", justify="left",
                                        wraplength=WRAP_LENGTH)
        self.summary_label.pack(fill="x", padx=PADDING, pady=PADDING)
        make_button(body, REPOSITORY_LABEL, lambda: open_url(REPOSITORY_URL)).pack(pady=PADDING)

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
            self._open_url(info.page_url)

    def render(self, snapshot: SessionSnapshot) -> None:
        """Show the update state and the matching action."""
        text, color = self._status()
        self.update_label.configure(text=text, text_color=color)
        label, enabled = self._button()
        self.action_button.configure(text=label, state="normal" if enabled else "disabled")
