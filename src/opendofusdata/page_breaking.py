"""The Brisage page: the broken objects, their breakings, and the classic / focus plus-value of the selected one."""

import sqlite3
from datetime import datetime

import customtkinter

from opendofusdata.app_config import load_config
from opendofusdata.breaking_detail_data import item_blocks, mean_coefficient
from opendofusdata.breaking_detail_text import DetailBlock
from opendofusdata.breaking_items import ItemSummary, group_by_item, item_summaries
from opendofusdata.breaking_texts import coefficient_text, plus_value_tag, runes_text
from opendofusdata.breaking_view_data import BreakingRow, breaking_rows
from opendofusdata.client_settings import price_mode_from_config
from opendofusdata.effects_csv import EFFECTS_FILE, RUNES_FILE, ItemEffects, Rune, load_item_effects, load_runes
from opendofusdata.price_book import PriceBook
from opendofusdata.price_rules import PRICE_LAST
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, elapsed_text
from opendofusdata.ui_table import Column, DataTable
from opendofusdata.ui_theme import (CARD_COLOR, CORNER_RADIUS, DETAIL_WIDTH, DOWN_COLOR, MUTED_COLOR, PADDING,
                                    SMALL_PADDING, TITLE_SIZE, TRANSPARENT, UP_COLOR)
from opendofusdata.ui_widgets import make_label
from opendofusdata.value_format import format_kamas, format_signed_kamas
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Brisage"
ITEM_COLUMNS = (Column("Objet", 240), Column("Prix HDV le plus bas", 170, True), Column("Coef. de brisage", 140, True),
                Column("Plus-value moyenne", 170, True), Column("Brisages", 90, True))
BREAKING_COLUMNS = (Column("Il y a", 110), Column("Quantité", 90, True), Column("Coefficient", 110, True),
                    Column("Valeur des runes", 170, True), Column("Plus-value", 150, True))
PLUS_VALUE_COLUMN = 3
BREAKINGS_TITLE = "Brisages de l'objet sélectionné"
NO_SELECTION_TEXT = "Sélectionne un objet pour voir ses brisages et sa plus-value en classique et en focus."
NO_EFFECTS_TEXT = "Effets de l'objet inconnus : lance « effects-update » pour les télécharger (DofusDB)."
WRAP_LENGTH = DETAIL_WIDTH - 4 * PADDING


class BreakingPage(ViewPage):
    """Left: broken objects, then the breakings of the selected one. Right: the plus-value by rune type."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, ITEM_COLUMNS, (PLUS_VALUE_COLUMN, True), 0, **options)
        self._by_item: dict[int, list[BreakingRow]] = {}
        self._effects: dict[int, ItemEffects] | None = None
        self._runes: list[Rune] = []
        self._detail_shown: object = None
        make_label(self.split.main, BREAKINGS_TITLE, color=MUTED_COLOR, anchor="w").pack(fill="x", pady=(PADDING, 0))
        self.breakings_table = DataTable(self.split.main, BREAKING_COLUMNS, lambda key: None, (0, True))
        self.breakings_table.pack(fill="both", expand=True)
        self._build_detail()

    def _build_detail(self) -> None:
        card = customtkinter.CTkScrollableFrame(self.split.detail, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True)
        self.name_label = make_label(card, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w",
                                     justify="left", wraplength=WRAP_LENGTH)
        self.name_label.pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.info_label = make_label(card, "", color=MUTED_COLOR, anchor="w", justify="left", wraplength=WRAP_LENGTH)
        self.info_label.pack(fill="x", padx=PADDING)
        self.blocks_frame = customtkinter.CTkFrame(card, fg_color=TRANSPARENT)
        self.blocks_frame.pack(fill="x", padx=PADDING, pady=PADDING)

    def _load_data(self) -> None:
        if self._effects is None:
            directory = self._context.data_directory
            self._effects = load_item_effects(directory / EFFECTS_FILE) or load_item_effects("data/" + EFFECTS_FILE)
            self._runes = load_runes(directory / RUNES_FILE) or load_runes("data/" + RUNES_FILE)

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """One row per broken object inside the window."""
        mode = price_mode_from_config(load_config(self._context.config_path))
        book = PriceBook.load(connection, server)
        rows = breaking_rows(connection, server, window, self._context.name_of, book, mode)
        self._by_item = group_by_item(rows)
        summaries = item_summaries(rows, lambda item_id: book.unit_price(item_id, PRICE_LAST))
        return [self._item_row(summary) for summary in summaries]

    def _item_row(self, summary: ItemSummary) -> TableRow:
        cells = (summary.name, format_kamas(summary.hdv_price), coefficient_text(summary.coefficient),
                 format_signed_kamas(summary.plus_value), str(summary.breakings))
        sort_values = (summary.name.casefold(), summary.hdv_price, summary.coefficient, summary.plus_value,
                       summary.breakings)
        return TableRow(summary.item_id, cells, sort_values, plus_value_tag(summary.plus_value))

    def _breaking_row(self, row: BreakingRow, now: datetime) -> TableRow:
        cells = (elapsed_text(row.moment, now), str(row.quantity), coefficient_text(row.coefficient),
                 runes_text(row), format_signed_kamas(row.plus_value))
        sort_values = (row.moment, row.quantity, row.coefficient, row.runes_value.total, row.plus_value)
        return TableRow(row.moment, cells, sort_values, plus_value_tag(row.plus_value))

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """List the breakings of the selected object and show its classic and focus plus-value."""
        own = self._by_item.get(key) if key is not None else None
        now = self._clock()
        self.breakings_table.set_rows([self._breaking_row(row, now) for row in own or []])
        if not own:
            self._render_detail(NO_SELECTION_TEXT, "", [])
            return
        self._load_data()
        info = f"Coefficient moyen {coefficient_text(mean_coefficient(own))} · {len(own)} brisage(s)"
        effects = self._effects.get(own[0].item_id)
        blocks = []
        if effects is not None:
            blocks = item_blocks(own, effects, self._runes, PriceBook.load(connection, server), self._context.name_of)
        self._render_detail(own[0].name, info if effects else NO_EFFECTS_TEXT, blocks)

    def _render_detail(self, name: str, info: str, blocks: list[DetailBlock]) -> None:
        if self._detail_shown == (name, info, blocks):
            return
        self._detail_shown = (name, info, blocks)
        self.name_label.configure(text=name)
        self.info_label.configure(text=info)
        for child in self.blocks_frame.winfo_children():
            child.destroy()
        for block in blocks:
            self._render_block(block)

    def _render_block(self, block: DetailBlock) -> None:
        make_label(self.blocks_frame, block.title, bold=True, anchor="w", justify="left",
                   wraplength=WRAP_LENGTH).pack(fill="x", pady=(SMALL_PADDING, 0))
        make_label(self.blocks_frame, "\n".join(block.lines), color=MUTED_COLOR, anchor="w", justify="left",
                   wraplength=WRAP_LENGTH).pack(fill="x")
        color = MUTED_COLOR if block.positive is None else (UP_COLOR if block.positive else DOWN_COLOR)
        make_label(self.blocks_frame, block.summary, bold=True, color=color, anchor="w", justify="left",
                   wraplength=WRAP_LENGTH).pack(fill="x", pady=(0, SMALL_PADDING))
