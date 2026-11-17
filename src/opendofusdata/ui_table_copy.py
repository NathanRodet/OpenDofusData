"""Click a table cell to copy its text to the clipboard (the favourite star of a name is left out)."""

import tkinter
from tkinter import ttk

from opendofusdata.pets_texts import FAVORITE_MARK

COPIED_TEXT = "Copié : {text}"
COPIED_MILLISECONDS = 1500
COPIED_COLOR, COPIED_BACKGROUND = "#e6e6e6", "#2b5d34"


def cell_text(tree: ttk.Treeview, event: tkinter.Event) -> str:
    """The text of the cell under the pointer, or an empty text outside the cells."""
    if tree.identify_region(event.x, event.y) != "cell":
        return ""
    item, column = tree.identify_row(event.y), tree.identify_column(event.x)
    if not item or not column:
        return ""
    return tree.set(item, int(column[1:]) - 1).removeprefix(FAVORITE_MARK).strip()


class CopyOnClick:
    """Copies the clicked cell and tells the player with a short label over the table."""

    def __init__(self, tree: ttk.Treeview) -> None:
        self._tree = tree
        self._notice = tkinter.Label(tree, fg=COPIED_COLOR, bg=COPIED_BACKGROUND, padx=8, pady=2)
        self._pending: str | None = None
        tree.bind("<ButtonRelease-1>", self._clicked, add="+")

    def _clicked(self, event: tkinter.Event) -> None:
        text = cell_text(self._tree, event)
        if not text:
            return
        self._tree.clipboard_clear()
        self._tree.clipboard_append(text)
        self._notice.configure(text=COPIED_TEXT.format(text=text))
        self._notice.place(relx=1.0, rely=1.0, x=-8, y=-8, anchor="se")
        if self._pending is not None:
            self._tree.after_cancel(self._pending)
        self._pending = self._tree.after(COPIED_MILLISECONDS, self._notice.place_forget)
