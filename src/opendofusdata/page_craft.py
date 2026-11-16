"""The Craft page: priced crafts, most profitable first; incomplete crafts and favourites on request."""

import sqlite3
from datetime import datetime

import customtkinter

from opendofusdata.breaking_texts import plus_value_tag
from opendofusdata.craft_economy import CraftRow, missing_prices
from opendofusdata.craft_view_data import craft_rows
from opendofusdata.pet_favorites_store import CRAFT_FAVORITES_KEY, load_favorites, toggle_favorite
from opendofusdata.pets_texts import FAVORITE_MARK
from opendofusdata.recipes_csv import DEFAULT_RECIPES_FILE, DEFAULT_RECIPES_PATH, Recipe, load_recipes
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, elapsed_text, parse_stored
from opendofusdata.ui_stats import StatList, StatRow
from opendofusdata.ui_table import Column
from opendofusdata.ui_theme import CARD_COLOR, CORNER_RADIUS, PADDING, SMALL_PADDING, TITLE_SIZE, TRANSPARENT
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
FAVORITE_LABEL = "Craft favori"
FAVORITES_ONLY_LABEL = "Favoris seulement"
INCOMPLETE_LABEL = "Afficher les crafts incomplets (un prix manque)"
SALE_PRICE_LABEL = "Prix HDV le plus bas"


class CraftPage(ViewPage):
    """Crafts whose prices are all known; incomplete ones appear on request or when they are favourites."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, COLUMNS, (MARGIN_COLUMN, True), 0, **options)
        self.period_bar.pack_forget()
        self._recipes: list[Recipe] | None = None
        self._craft_rows: dict[int, CraftRow] = {}
        self._favorites: set[int] = set()
        self._build_filters()
        card = customtkinter.CTkScrollableFrame(self.split.detail, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True)
        self.name_label = make_label(card, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w", wraplength=300)
        self.name_label.pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.favorite_box = customtkinter.CTkCheckBox(card, text=FAVORITE_LABEL, command=self._toggle_favorite)
        self.favorite_box.pack(anchor="w", padx=PADDING)
        self.favorite_box.configure(state="disabled")
        self.ingredients_title = make_card_title(card, "")
        self.ingredients_title.pack(fill="x", padx=PADDING, pady=(SMALL_PADDING, SMALL_PADDING))
        self.ingredients_list = StatList(card)
        self.ingredients_list.pack(fill="x", padx=PADDING, pady=(0, PADDING))

    def _build_filters(self) -> None:
        bar = customtkinter.CTkFrame(self.frame, fg_color=TRANSPARENT, corner_radius=0)
        bar.pack(before=self.split, fill="x", padx=PADDING, pady=(0, SMALL_PADDING))
        self.favorites_only = customtkinter.CTkCheckBox(bar, text=FAVORITES_ONLY_LABEL, command=self.refresh)
        self.favorites_only.pack(side="left")
        self.incomplete_box = customtkinter.CTkCheckBox(bar, text=INCOMPLETE_LABEL, command=self.refresh)
        self.incomplete_box.pack(side="left", padx=PADDING)

    def _toggle_favorite(self) -> None:
        if self._selected is not None:
            toggle_favorite(self._context.config_path, int(self._selected), CRAFT_FAVORITES_KEY)
            self.refresh()

    def _is_listed(self, row: CraftRow) -> bool:
        """Complete crafts always; incomplete ones when asked for or favourite; only favourites when filtered."""
        if self.favorites_only.get():
            return row.item_id in self._favorites
        return row.margin is not None or bool(self.incomplete_box.get()) or row.item_id in self._favorites

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """The crafts to list (see `_is_listed`), the complete ones first."""
        if self._recipes is None:
            self._recipes = (load_recipes(self._context.data_directory / DEFAULT_RECIPES_FILE)
                             or load_recipes(DEFAULT_RECIPES_PATH))
        rows = craft_rows(connection, server, self._recipes)
        self._craft_rows = {row.item_id: row for row in rows}
        self.notice.configure(text="" if self._recipes else NO_RECIPES_TEXT)
        now = self._clock()
        self._favorites = load_favorites(self._context.config_path, CRAFT_FAVORITES_KEY)
        return [self._table_row(row, now) for row in rows if self._is_listed(row)]

    def _table_row(self, row: CraftRow, now: datetime) -> TableRow:
        percent = "" if row.margin_percent is None else PERCENT_FORMAT.format(row.margin_percent)
        name = (FAVORITE_MARK if row.item_id in self._favorites else "") + self._context.name_of(row.item_id)
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
            self.favorite_box.deselect()
            self.favorite_box.configure(state="disabled")
            self.name_label.configure(text=NO_SELECTION_TEXT)
            self.ingredients_title.configure(text=MISSING_TITLE if self._missing_rows() else "")
            self.ingredients_list.set_rows(self._missing_rows())
            return
        self.name_label.configure(text=self._context.name_of(row.item_id))
        self.favorite_box.configure(state="normal")
        (self.favorite_box.select if row.item_id in self._favorites else self.favorite_box.deselect)()
        self.ingredients_title.configure(text=INGREDIENTS_TITLE)
        sale = UNKNOWN_PRICE_TEXT if row.sale_price is None else f"{format_kamas(row.sale_price)} kamas"
        self.ingredients_list.set_rows([(SALE_PRICE_LABEL, sale, None),
                                        *(self._ingredient_row(*ingredient) for ingredient in row.ingredients)])

    def _missing_rows(self) -> list[StatRow]:
        blocked = missing_prices(self._craft_rows.values(), MISSING_LIMIT)
        return [(self._context.name_of(item), f"{count} craft(s)", None) for item, count in blocked]
