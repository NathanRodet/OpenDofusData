"""The Familiers "Couverture" tab: coefficients known out of the possible resources, and the missing ones."""

import tkinter

import customtkinter

from opendofusdata.pet_coverage import Coverage, MissingItem
from opendofusdata.table_model import TableRow
from opendofusdata.ui_stats import StatList
from opendofusdata.ui_table import Column, DataTable
from opendofusdata.ui_theme import PADDING, SMALL_PADDING, TRANSPARENT
from opendofusdata.ui_widgets import make_card_title

ALL_CATEGORIES = "Toutes les catégories"
MISSING_TITLE = "Ressources sans coefficient"
COLUMNS = (Column("Objet", 300), Column("Catégorie", 200))
CATEGORY_MENU_WIDTH = 240


def percent_text(coverage: Coverage) -> str:
    """The covered share, e.g. '40 %' (empty when nothing is possible)."""
    return f"{100 * coverage.covered / coverage.total:.0f} %" if coverage.total else ""


class CoverageView(customtkinter.CTkFrame):
    """A summary, a category filter and the table of the resources without a coefficient."""

    def __init__(self, parent: tkinter.Misc) -> None:
        super().__init__(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._coverage = Coverage(0, 0, ())
        self._text = ""
        self.summary = StatList(self)
        self.summary.pack(fill="x", padx=PADDING, pady=(0, SMALL_PADDING))
        header = customtkinter.CTkFrame(self, fg_color=TRANSPARENT, corner_radius=0)
        header.pack(fill="x", padx=PADDING, pady=SMALL_PADDING)
        make_card_title(header, MISSING_TITLE).pack(side="left")
        self.category_menu = customtkinter.CTkOptionMenu(header, values=[ALL_CATEGORIES], width=CATEGORY_MENU_WIDTH,
                                                         command=lambda _choice: self._show())
        self.category_menu.pack(side="right")
        self.table = DataTable(self, COLUMNS, lambda key: None, (0, False))
        self.table.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))

    def set_coverage(self, coverage: Coverage, text: str = "") -> None:
        """Show this coverage, filtered by the category menu and by the typed text."""
        self._coverage, self._text = coverage, text.strip().casefold()
        values = [ALL_CATEGORIES, *coverage.categories()]
        if tuple(values) != tuple(self.category_menu.cget("values")):
            self.category_menu.configure(values=values)
            if self.category_menu.get() not in values:
                self.category_menu.set(ALL_CATEGORIES)
        self._show()

    def _matches(self, item: MissingItem) -> bool:
        category = self.category_menu.get()
        return category in (ALL_CATEGORIES, item.category) and self._text in item.name.casefold()

    def _show(self) -> None:
        coverage = self._coverage
        self.summary.set_rows([("Ressources avec un coefficient", f"{coverage.covered} / {coverage.total}", None),
                               ("Part couverte", percent_text(coverage), None),
                               ("Sans coefficient", str(len(coverage.missing)), None)])
        rows = [TableRow(item.item_id, (item.name, item.category), (item.name.casefold(), item.category))
                for item in coverage.missing if self._matches(item)]
        self.table.set_rows(rows)
