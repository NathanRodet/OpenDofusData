"""Builds the pages of the window, in menu order."""

import customtkinter

from opendofusdata.admin_settings import AdminSettings, load_admin_settings
from opendofusdata.env_file import env_file_path
from opendofusdata.page_admin import AdminPage
from opendofusdata.page_breaking import BreakingPage
from opendofusdata.page_craft import CraftPage
from opendofusdata.page_hdv import HdvPage
from opendofusdata.page_logs import LogsPage
from opendofusdata.page_pets import PetsPage
from opendofusdata.page_settings import SettingsPage
from opendofusdata.settings_names import Refresh
from opendofusdata.ui_widgets import Page
from opendofusdata.window_context import WindowContext

PAGE_NAMES = ("HDV", "Brisage", "Craft", "Familiers", "Logs", "Réglages")
SETTINGS_PAGE = "Réglages"
ADMIN_PAGE = "Administration"


def admin_settings(context: WindowContext) -> AdminSettings | None:
    """The administrator settings of this PC (from the .env next to config.json), or None for a normal player."""
    return load_admin_settings(env_file_path(context.config_path))


def build_pages(parent: customtkinter.CTkBaseClass, context: WindowContext,
                refresh: Refresh | None = None) -> dict[str, Page]:
    """Create every page inside `parent`, keyed by menu name (PAGE_NAMES, then Administration if configured)."""
    pages: dict[str, Page] = {
        "HDV": HdvPage(parent, context),
        "Brisage": BreakingPage(parent, context),
        "Craft": CraftPage(parent, context),
        "Familiers": PetsPage(parent, context),
        "Logs": LogsPage(parent, context),
        SETTINGS_PAGE: SettingsPage(parent, context, **({"refresh": refresh} if refresh else {})),
    }
    settings = admin_settings(context)
    if settings is not None:
        pages[ADMIN_PAGE] = AdminPage(parent, context, settings)
    return pages
