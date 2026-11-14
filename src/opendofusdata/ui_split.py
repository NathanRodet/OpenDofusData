"""A main area with a detail panel that sits on the right when wide and below when narrow."""

import tkinter

import customtkinter

from opendofusdata.ui_theme import DETAIL_WIDTH, PADDING, SPLIT_BREAKPOINT, TRANSPARENT

LAYOUT_RIGHT = "right"
LAYOUT_BELOW = "below"


class SplitLayout(customtkinter.CTkFrame):
    """Exposes `main` and `detail`; `layout_mode` tells where the detail panel currently is."""

    def __init__(self, parent: tkinter.Misc) -> None:
        super().__init__(parent, fg_color=TRANSPARENT, corner_radius=0)
        self.main = customtkinter.CTkFrame(self, fg_color=TRANSPARENT, corner_radius=0)
        self.detail = customtkinter.CTkFrame(self, fg_color=TRANSPARENT, corner_radius=0)
        self.layout_mode = ""
        self.relayout(SPLIT_BREAKPOINT)
        self.bind("<Configure>", lambda _event: self.relayout(self.winfo_toplevel().winfo_width()))

    def relayout(self, width: int) -> None:
        """Place the detail panel right of the main area from SPLIT_BREAKPOINT wide, below it otherwise."""
        mode = LAYOUT_RIGHT if width >= SPLIT_BREAKPOINT else LAYOUT_BELOW
        if mode == self.layout_mode:
            return
        self.layout_mode = mode
        for child in (self.main, self.detail):
            child.grid_forget()
        if mode == LAYOUT_RIGHT:
            self._place_right()
        else:
            self._place_below()

    def _place_right(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=DETAIL_WIDTH)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0, minsize=0)
        self.main.grid(row=0, column=0, sticky="nsew")
        self.detail.grid(row=0, column=1, sticky="nsew", padx=(PADDING, 0))

    def _place_below(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=0)
        self.grid_rowconfigure(0, weight=3)
        self.grid_rowconfigure(1, weight=2)
        self.main.grid(row=0, column=0, sticky="nsew")
        self.detail.grid(row=1, column=0, sticky="nsew", pady=(PADDING, 0))
