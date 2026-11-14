"""Brisage tab 2: what was paid for each broken object (editable) and what its runes brought."""

import sqlite3
from datetime import datetime

import customtkinter

from opendofusdata.app_config import load_config
from opendofusdata.breaking_texts import MODIFIED_SUFFIX, coefficient_text, plus_value_tag, price_text, runes_text
from opendofusdata.breaking_view_data import BreakingRow, breaking_rows
from opendofusdata.client_settings import price_mode_from_config
from opendofusdata.price_book import PriceBook
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, elapsed_text
from opendofusdata.timeutil import format_utc
from opendofusdata.ui_table import Column
from opendofusdata.ui_theme import CARD_COLOR, CORNER_RADIUS, MUTED_COLOR, PADDING, SMALL_PADDING, TITLE_SIZE
from opendofusdata.ui_widgets import make_label
from opendofusdata.user_prices import PURCHASE_PRICES_KEY, load_prices, parse_kamas, store_price
from opendofusdata.value_format import format_kamas, format_signed_kamas
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Achats et résultat des brisages"
COLUMNS = (Column("Il y a", 100), Column("Objet", 210), Column("Quantité", 90, True), Column("Coefficient", 100, True),
           Column("Prix d'achat à l'unité (double-clic)", 250, True), Column("Valeur des runes", 160, True),
           Column("Gain", 130, True))
PRICE_COLUMN = 4
NAME_COLUMN = 1
BAD_PRICE_NOTICE = "Prix illisible : écris un nombre (95000, 95 000, 1,5k). Vide = reprendre le prix de l'HDV du moment."
SAVE_FAILED_NOTICE = "Le prix n'a pas pu être enregistré (voir le journal)."
NO_SELECTION_TEXT = "Sélectionne un brisage pour voir la rentabilité de chaque rune."
PERCENT = 100


def entry_key(row: BreakingRow) -> str:
    """The identity of one breaking: object and capture time."""
    return f"{row.item_id}|{format_utc(row.moment)}"


class PurchasesPage(ViewPage):
    """One row per breaking; the purchase price defaults to the HDV price at that moment."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, COLUMNS, (0, True), NAME_COLUMN,
                         editable=(PRICE_COLUMN,), on_edit=self.price_typed, **options)
        self._breaking_rows: dict[str, BreakingRow] = {}
        self._build_detail()

    def _build_detail(self) -> None:
        card = customtkinter.CTkScrollableFrame(self.split.detail, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True)
        self.name_label = make_label(card, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w", wraplength=300)
        self.name_label.pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.totals_label = make_label(card, "", anchor="w", justify="left")
        self.totals_label.pack(fill="x", padx=PADDING)
        self.runes_label = make_label(card, "", color=MUTED_COLOR, anchor="w", justify="left")
        self.runes_label.pack(fill="x", padx=PADDING, pady=PADDING)

    def price_typed(self, key: object, column: int, text: str) -> None:
        """Save the purchase price typed for one breaking (empty text goes back to the HDV price of the moment)."""
        try:
            price = parse_kamas(text.replace(MODIFIED_SUFFIX, ""))
        except ValueError:
            self.notice.configure(text=BAD_PRICE_NOTICE)
            return
        saved = store_price(self._context.config_path, PURCHASE_PRICES_KEY, str(key), price)
        self.notice.configure(text="" if saved else SAVE_FAILED_NOTICE)
        self.refresh()

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """One row per breaking inside the window, with its purchase price and gain."""
        mode = price_mode_from_config(load_config(self._context.config_path))
        book = PriceBook.load(connection, server)
        rows = breaking_rows(connection, server, window, self._context.name_of, book, mode)
        typed = load_prices(self._context.config_path, PURCHASE_PRICES_KEY)
        self._breaking_rows = {entry_key(row): row for row in rows}
        now = self._clock()
        table = [self._table_row(row, typed, book, now) for row in rows]
        self._show_totals(rows, typed, book)
        return table

    def _unit_price(self, row: BreakingRow, typed: dict[str, float], book: PriceBook) -> float | None:
        key = entry_key(row)
        return typed[key] if key in typed else book.price_at(row.item_id, row.moment)

    def _gain(self, row: BreakingRow, unit: float | None) -> float | None:
        if unit is None or row.runes_value.total is None:
            return None
        return row.runes_value.total - unit * row.quantity

    def _table_row(self, row: BreakingRow, typed: dict[str, float], book: PriceBook, now: datetime) -> TableRow:
        unit = self._unit_price(row, typed, book)
        gain = self._gain(row, unit)
        cells = (elapsed_text(row.moment, now), row.name, str(row.quantity), coefficient_text(row.coefficient),
                 price_text(unit, entry_key(row) in typed), runes_text(row), format_signed_kamas(gain))
        sort_values = (row.moment, row.name.casefold(), row.quantity, row.coefficient, unit,
                       row.runes_value.total, gain)
        return TableRow(entry_key(row), cells, sort_values, plus_value_tag(gain))

    def _show_totals(self, rows: list[BreakingRow], typed: dict[str, float], book: PriceBook) -> None:
        spent = got = 0.0
        for row in rows:
            unit = self._unit_price(row, typed, book)
            if unit is not None and row.runes_value.total is not None:
                spent += unit * row.quantity
                got += row.runes_value.total
        self.totals_label.configure(text=(f"Dépensé : {format_kamas(spent)} kamas\n"
                                          f"Tiré des runes : {format_kamas(got)} kamas\n"
                                          f"Gain total : {format_signed_kamas(got - spent)} kamas"))

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """List the runes obtained by the selected breaking."""
        row = self._breaking_rows.get(str(key)) if key is not None else None
        if row is None:
            self.name_label.configure(text=NO_SELECTION_TEXT)
            self.runes_label.configure(text="")
            return
        self.name_label.configure(text=row.name)
        self.runes_label.configure(text="\n".join(self._rune_lines(connection, server, row)))

    def _rune_lines(self, connection: sqlite3.Connection, server: str, row: BreakingRow) -> list[str]:
        """One line per rune: count, unit price, value and share of the total, best first."""
        mode = price_mode_from_config(load_config(self._context.config_path))
        book = PriceBook.load(connection, server)
        priced = [(rune, count, book.unit_price(rune, mode)) for rune, count in row.runes]
        total = sum(price * count for _, count, price in priced if price is not None)
        priced.sort(key=lambda entry: -(entry[2] or 0) * entry[1])
        return [self._rune_line(rune, count, price, total) for rune, count, price in priced] or ["Aucune rune"]

    def _rune_line(self, rune: int, count: int, price: float | None, total: float) -> str:
        name = self._context.name_of(rune)
        if price is None:
            return f"{name} ×{count} : prix inconnu"
        share = round(price * count * PERCENT / total) if total else 0
        return f"{name} ×{count} : {format_kamas(price)} l'unité, {format_kamas(price * count)} kamas ({share} %)"
