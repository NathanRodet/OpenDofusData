"""Builds the pages of the window, in menu order."""

import customtkinter

from opendofusdata.page_breaking import BreakingPage
from opendofusdata.page_hdv import HdvPage
from opendofusdata.page_logs import LogsPage
from opendofusdata.page_pets import PetsPage
from opendofusdata.page_settings import SettingsPage
from opendofusdata.ui_widgets import Page
from opendofusdata.window_context import WindowContext

PAGE_NAMES = ("HDV", "Brisage", "Familiers", "Logs", "Réglages")
SETTINGS_PAGE = "Réglages"


def build_pages(parent: customtkinter.CTkBaseClass, context: WindowContext) -> dict[str, Page]:
    """Create every page inside `parent`, keyed by menu name (same order as PAGE_NAMES)."""
    return {
        "HDV": HdvPage(parent, context),
        "Brisage": BreakingPage(parent, context),
        "Familiers": PetsPage(parent, context),
        "Logs": LogsPage(parent, context),
        SETTINGS_PAGE: SettingsPage(parent, context),
    }
