"""Brisage tab 3: runes a breaking should give by the formula, for every object with a known HDV price."""

import sqlite3

import customtkinter

from opendofusdata.breaking_texts import coefficient_text, plus_value_tag
from opendofusdata.effects_csv import EFFECTS_FILE, RUNES_FILE, ItemEffects, Rune, load_item_effects, load_runes
from opendofusdata.table_model import TableRow
from opendofusdata.theory_view_data import TheoryRow, theory_rows
from opendofusdata.time_filters import Window
from opendofusdata.ui_table import Column
from opendofusdata.ui_theme import CARD_COLOR, CORNER_RADIUS, MUTED_COLOR, PADDING, SMALL_PADDING, TITLE_SIZE
from opendofusdata.ui_widgets import make_label
from opendofusdata.user_prices import THEORY_COEFFICIENTS_KEY, load_prices, parse_kamas, store_price
from opendofusdata.value_format import format_kamas, format_signed_kamas
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Brisage théorique (formule, prix moyens des runes)"
COLUMNS = (Column("Objet", 230), Column("Prix HDV le plus bas", 160, True),
           Column("Coefficient % (double-clic)", 190, True), Column("Valeur attendue des runes", 190, True),
           Column("Plus-value attendue", 160, True), Column("Valeur réelle moyenne", 170, True),
           Column("Brisages", 90, True))
COEFFICIENT_COLUMN = 2
PLUS_VALUE_COLUMN = 4
PERCENT = 100
MODIFIED = " (modifié)"
OBSERVED = " (observé)"
NO_SELECTION_TEXT = "Sélectionne un objet pour voir les runes attendues."
NO_DATA_TEXT = "Pas d'effets : lance « effects-update » pour télécharger les effets des objets (DofusDB)."
BAD_COEFFICIENT_NOTICE = "Coefficient illisible : écris un nombre entre 0 et 100 (ex. 45). Vide = valeur par défaut."
UNKNOWN_PRICE_TEXT = "prix inconnu"


class TheoryPage(ViewPage):
    """Expected runes per object; the coefficient can be typed, else the mean of the real breakings is used."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, COLUMNS, (PLUS_VALUE_COLUMN, True), 0,
                         editable=(COEFFICIENT_COLUMN,), on_edit=self.coefficient_typed, **options)
        self.period_bar.pack_forget()
        self._effects: dict[int, ItemEffects] | None = None
        self._runes: list[Rune] = []
        self._theory_rows: dict[int, TheoryRow] = {}
        card = customtkinter.CTkScrollableFrame(self.split.detail, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True)
        self.name_label = make_label(card, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w", wraplength=300)
        self.name_label.pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.runes_label = make_label(card, "", color=MUTED_COLOR, anchor="w", justify="left")
        self.runes_label.pack(fill="x", padx=PADDING, pady=(0, PADDING))

    def coefficient_typed(self, key: object, column: int, text: str) -> None:
        """Save the coefficient (in %) typed for an object; empty text goes back to the observed or default one."""
        cleaned = text.replace(MODIFIED, "").replace(OBSERVED, "").replace("%", "")
        try:
            percent = parse_kamas(cleaned)
        except ValueError:
            percent = -1.0
        if percent is not None and not 0 <= percent <= PERCENT:
            self.notice.configure(text=BAD_COEFFICIENT_NOTICE)
            return
        store_price(self._context.config_path, THEORY_COEFFICIENTS_KEY, str(key), percent)
        self.notice.configure(text="")
        self.refresh()

    def _load_data(self) -> None:
        if self._effects is None:
            directory = self._context.data_directory
            self._effects = load_item_effects(directory / EFFECTS_FILE) or load_item_effects("data/" + EFFECTS_FILE)
            self._runes = load_runes(directory / RUNES_FILE) or load_runes("data/" + RUNES_FILE)

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """One row per object with a price and at least one rune."""
        self._load_data()
        percents = load_prices(self._context.config_path, THEORY_COEFFICIENTS_KEY)
        typed = {int(item): percent / PERCENT for item, percent in percents.items() if item.isdigit()}
        rows = theory_rows(connection, server, self._effects, self._runes, typed, self._context.name_of)
        self._theory_rows = {row.item_id: row for row in rows}
        self.notice.configure(text="" if self._effects else NO_DATA_TEXT)
        return [self._table_row(row, row.item_id in typed) for row in rows]

    def _table_row(self, row: TheoryRow, typed: bool) -> TableRow:
        name = self._context.name_of(row.item_id)
        suffix = MODIFIED if typed else (OBSERVED if row.observed else "")
        real = "" if row.real_runes_value is None else format_kamas(row.real_runes_value)
        cells = (name, format_kamas(row.hdv_price), coefficient_text(row.coefficient) + suffix,
                 format_kamas(row.runes_value), format_signed_kamas(row.plus_value), real, str(row.breakings))
        sort_values = (name.casefold(), row.hdv_price, row.coefficient, row.runes_value, row.plus_value,
                       row.real_runes_value, row.breakings)
        return TableRow(row.item_id, cells, sort_values, plus_value_tag(row.plus_value))

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """List the expected runes of the selected object with their average price."""
        row = self._theory_rows.get(key) if key is not None else None
        if row is None:
            self.name_label.configure(text=NO_SELECTION_TEXT)
            self.runes_label.configure(text="")
            return
        self.name_label.configure(text=self._context.name_of(row.item_id))
        lines = [self._rune_line(rune, count, price) for rune, count, price in row.runes]
        self.runes_label.configure(text="\n".join(lines))

    def _rune_line(self, rune: int, count: float, price: float | None) -> str:
        shown = UNKNOWN_PRICE_TEXT if price is None else f"{format_kamas(price)} l'unité, {format_kamas(count * price)} kamas"
        return f"{self._context.name_of(rune)} ×{count:.2f} : {shown}"
