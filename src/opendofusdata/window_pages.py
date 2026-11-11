"""Builds the pages of the window, in menu order."""

import webbrowser

import customtkinter

from opendofusdata.app_links import REPOSITORY_URL
from opendofusdata.page_about import AboutPage
from opendofusdata.page_data import DataPage
from opendofusdata.page_home import HomePage
from opendofusdata.page_logs import LogsPage
from opendofusdata.page_settings import SettingsPage
from opendofusdata.ui_widgets import Page
from opendofusdata.window_context import WindowContext

PAGE_NAMES = ("Accueil", "Données", "Logs", "Réglages", "À propos")


def open_repository() -> None:
    """Open the project page in the default browser."""
    webbrowser.open(REPOSITORY_URL)


def build_pages(parent: customtkinter.CTkBaseClass, context: WindowContext) -> dict[str, Page]:
    """Create every page inside `parent`, keyed by menu name (same order as PAGE_NAMES)."""
    return {
        "Accueil": HomePage(parent, context.open_online),
        "Données": DataPage(parent, context),
        "Logs": LogsPage(parent, context),
        "Réglages": SettingsPage(parent, context),
        "À propos": AboutPage(parent, open_repository),
    }
