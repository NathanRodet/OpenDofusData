"""The À propos page: what the tool is, what it collects, and that nothing leaves the machine."""

from collections.abc import Callable
from importlib import metadata

import customtkinter

from opendofusdata.capture_session import SessionSnapshot
from opendofusdata.ui_theme import MUTED_COLOR, PADDING, WRAP_LENGTH
from opendofusdata.ui_widgets import add_title, make_button, make_card, make_label, make_page

PACKAGE_NAME = "open-dofus-data"
DEVELOPMENT_VERSION = "dev"
TITLE = "À propos"
SUMMARY = (
    "Outil libre et open source qui lit passivement le trafic réseau de Dofus 3.\n"
    "Catégories collectées : HDV (recyclage, brisage et expérience des pets arrivent bientôt).\n"
    "Rien n'est envoyé hors de ta machine dans cette version."
)
REPOSITORY_LABEL = "Voir le dépôt"


def app_version() -> str:
    """The installed package version, or 'dev' when running from a source checkout."""
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return DEVELOPMENT_VERSION


class AboutPage:
    """Static information page."""

    def __init__(self, parent: customtkinter.CTkBaseClass, open_repository: Callable[[], None]) -> None:
        self.frame, body = make_page(parent)
        add_title(body, TITLE)
        self.version_label = make_label(body, f"Version {app_version()}", color=MUTED_COLOR, anchor="w")
        self.version_label.pack(fill="x", pady=(0, PADDING))
        card = make_card(body)
        self.summary_label = make_label(card, SUMMARY, anchor="w", justify="left", wraplength=WRAP_LENGTH)
        self.summary_label.pack(fill="x", padx=PADDING, pady=PADDING)
        make_button(body, REPOSITORY_LABEL, open_repository).pack(pady=PADDING)

    def render(self, snapshot: SessionSnapshot) -> None:
        """Nothing changes on this page."""
