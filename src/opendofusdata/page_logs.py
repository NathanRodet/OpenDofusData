"""The Logs page: the captured records as fixed-width columns, shown only when the player asks."""

import customtkinter

from opendofusdata.capture_session import SessionSnapshot
from opendofusdata.log_feed import LOG_COLUMNS, MAX_LOG_LINES, LogEntry, format_log_line, format_log_row
from opendofusdata.ui_theme import (
    ACCENT_COLOR, LOG_COLOR, MONOSPACE_FONT, MONOSPACE_SIZE, MUTED_COLOR, PADDING, SMALL_PADDING,
    SWITCH_WIDTH, WRAP_LENGTH,
)
from opendofusdata.ui_widgets import add_title, make_card, make_label, make_page
from opendofusdata.window_context import WindowContext

TITLE = "Logs"
SUBTITLE = f"Les données captées, de la plus récente à la plus ancienne ({MAX_LOG_LINES} lignes au plus)."
SWITCH_LABEL = "Afficher les logs"
HIDDEN_HINT = "Logs masqués. Active l'interrupteur pour voir ce que l'outil capte."
LINE_BREAK = "\n"


class LogsPage:
    """A switch (off by default) and a read-only monospace table of the feed."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext) -> None:
        self._context = context
        self._shown: list[LogEntry] = []
        self._names_used = context.name_of
        self.frame, body = make_page(parent)
        add_title(body, TITLE, SUBTITLE)
        self.switch = self._add_switch_row(body)
        font = customtkinter.CTkFont(family=MONOSPACE_FONT, size=MONOSPACE_SIZE)
        self.header_label = make_label(body, format_log_line(LOG_COLUMNS), MONOSPACE_SIZE,
                                       color=MUTED_COLOR, anchor="w")
        self.header_label.configure(font=font)
        self.text_box = customtkinter.CTkTextbox(body, font=font, fg_color=LOG_COLOR, wrap="none",
                                                 state="disabled")
        self.hint_label = make_label(body, HIDDEN_HINT, color=MUTED_COLOR, wraplength=WRAP_LENGTH)
        self._show_hint()

    def _add_switch_row(self, body: customtkinter.CTkFrame) -> customtkinter.CTkSwitch:
        card = make_card(body)
        make_label(card, SWITCH_LABEL, anchor="w").pack(side="left", padx=PADDING, pady=PADDING)
        switch = customtkinter.CTkSwitch(card, text="", width=SWITCH_WIDTH, progress_color=ACCENT_COLOR,
                                         command=self._toggled)
        switch.pack(side="right", padx=PADDING)
        return switch

    def _toggled(self) -> None:
        visible = bool(self.switch.get())
        self._context.session.feed.set_visible(visible)
        self._shown = []
        self._set_text("")
        if visible:
            self._show_table()
        else:
            self._show_hint()

    def _show_hint(self) -> None:
        self.header_label.pack_forget()
        self.text_box.pack_forget()
        self.hint_label.pack(pady=PADDING * 2)

    def _show_table(self) -> None:
        self.hint_label.pack_forget()
        self.header_label.pack(fill="x", padx=SMALL_PADDING)
        self.text_box.pack(fill="both", expand=True)

    def _set_text(self, text: str) -> None:
        self.text_box.configure(state="normal")
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", text)
        self.text_box.configure(state="disabled")

    def log_text(self) -> str:
        """The text currently shown in the table (empty while the logs are hidden)."""
        return self.text_box.get("1.0", "end").strip(LINE_BREAK)

    def render(self, snapshot: SessionSnapshot) -> None:
        """Rewrite the table only when the feed changed."""
        entries = self._context.session.feed.entries()
        names = self._context.name_of
        if not self.switch.get() or (entries == self._shown and names is self._names_used):
            return
        lines = (format_log_line(format_log_row(entry, names)) for entry in entries)
        self._set_text(LINE_BREAK.join(lines))
        self._shown, self._names_used = entries, names
