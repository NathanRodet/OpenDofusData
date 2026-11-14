"""The Craft page: crafts that can be priced with the collected prices, most profitable first."""

import sqlite3
from datetime import datetime

import customtkinter

from opendofusdata.breaking_texts import plus_value_tag
from opendofusdata.craft_economy import CraftRow, missing_prices
from opendofusdata.craft_view_data import craft_rows
from opendofusdata.recipes_csv import DEFAULT_RECIPES_FILE, DEFAULT_RECIPES_PATH, Recipe, load_recipes
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, elapsed_text, parse_stored
from opendofusdata.ui_stats import StatList, StatRow
from opendofusdata.ui_table import Column
from opendofusdata.ui_theme import CARD_COLOR, CORNER_RADIUS, PADDING, SMALL_PADDING, TITLE_SIZE
from opendofusdata.ui_widgets import make_card_title, make_label
from opendofusdata.value_format import format_kamas, format_signed_kamas
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Crafts rentables"
COLUMNS = (Column("Objet", 240), Column("Prix HDV le plus bas", 170, True), Column("Coût des ressources", 170, True),
           Column("Marge", 140, True), Column("Marge %", 100, True), Column("Prix le plus ancien", 150))
MARGIN_COLUMN = 3
NO_SELECTION_TEXT = "Sélectionne un craft pour voir ses ressources."
NO_RECIPES_TEXT = "Aucune recette : lance « recipes-update » pour télécharger les recettes (DofusDB)."
PERCENT_FORMAT = "{:+.0f} %"
UNKNOWN_PRICE_TEXT = "prix inconnu"
MISSING_LIMIT = 15
MISSING_TITLE = "À relever à l'HDV (ils bloquent le plus de crafts)"
INGREDIENTS_TITLE = "Ressources"


class CraftPage(ViewPage):
    """One row per craft whose sale price and resource prices are all known."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, COLUMNS, (MARGIN_COLUMN, True), 0, **options)
        self.period_bar.pack_forget()
        self._recipes: list[Recipe] | None = None
        self._craft_rows: dict[int, CraftRow] = {}
        card = customtkinter.CTkScrollableFrame(self.split.detail, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True)
        self.name_label = make_label(card, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w", wraplength=300)
        self.name_label.pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.ingredients_title = make_card_title(card, "")
        self.ingredients_title.pack(fill="x", padx=PADDING, pady=(SMALL_PADDING, SMALL_PADDING))
        self.ingredients_list = StatList(card)
        self.ingredients_list.pack(fill="x", padx=PADDING, pady=(0, PADDING))

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """The priced crafts, left out of the table when a price is missing."""
        if self._recipes is None:
            self._recipes = (load_recipes(self._context.data_directory / DEFAULT_RECIPES_FILE)
                             or load_recipes(DEFAULT_RECIPES_PATH))
        rows = craft_rows(connection, server, self._recipes)
        self._craft_rows = {row.item_id: row for row in rows}
        self.notice.configure(text="" if self._recipes else NO_RECIPES_TEXT)
        now = self._clock()
        return [self._table_row(row, now) for row in rows if row.margin is not None]

    def _table_row(self, row: CraftRow, now: datetime) -> TableRow:
        percent = "" if row.margin_percent is None else PERCENT_FORMAT.format(row.margin_percent)
        name = self._context.name_of(row.item_id)
        age = "" if row.oldest_seen is None else elapsed_text(parse_stored(row.oldest_seen), now)
        cells = (name, format_kamas(row.sale_price), format_kamas(row.cost), format_signed_kamas(row.margin), percent,
                 age)
        sort_values = (name.casefold(), row.sale_price, row.cost, row.margin, row.margin_percent,
                       row.oldest_seen or "")
        return TableRow(row.item_id, cells, sort_values, plus_value_tag(row.margin))

    def _ingredient_row(self, item: int, quantity: int, price: float | None) -> StatRow:
        shown = UNKNOWN_PRICE_TEXT if price is None else f"{format_kamas(price)} l'unité"
        return (f"{self._context.name_of(item)} ×{quantity}", shown, None)

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """List the resources of the selected craft with their unit price."""
        row = self._craft_rows.get(key) if key is not None else None
        if row is None:
            self.name_label.configure(text=NO_SELECTION_TEXT)
            self.ingredients_title.configure(text=MISSING_TITLE if self._missing_rows() else "")
            self.ingredients_list.set_rows(self._missing_rows())
            return
        self.name_label.configure(text=self._context.name_of(row.item_id))
        self.ingredients_title.configure(text=INGREDIENTS_TITLE)
        self.ingredients_list.set_rows([self._ingredient_row(*ingredient) for ingredient in row.ingredients])

    def _missing_rows(self) -> list[StatRow]:
        blocked = missing_prices(self._craft_rows.values(), MISSING_LIMIT)
        return [(self._context.name_of(item), f"{count} craft(s)", None) for item, count in blocked]
