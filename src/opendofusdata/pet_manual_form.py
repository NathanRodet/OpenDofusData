"""The Familiers form: search a resource and add the experience that x of them gave."""

import tkinter
from collections.abc import Callable

import customtkinter

from opendofusdata.ui_theme import (ACCENT_COLOR, CARD_COLOR, CORNER_RADIUS, ERROR_COLOR, MUTED_COLOR, PADDING, SMALL_PADDING,
                                    SUCCESS_COLOR)
from opendofusdata.ui_widgets import make_button, make_label

FORM_TITLE = "Ajouter de l'XP pour une ressource"
ITEM_PLACEHOLDER = "Rechercher un objet"
UNITS_PLACEHOLDER = "Nombre de ressources"
EXPERIENCE_PLACEHOLDER = "XP obtenue"
ADD_TEXT = "Ajouter"
REMOVE_TEXT = "Retirer mes saisies"
UNKNOWN_ITEM_MESSAGE = "Choisis un objet dans la liste de recherche."
BAD_NUMBER_MESSAGE = "Écris deux nombres entiers positifs (ressources et XP)."
ADDED_MESSAGE = "Ajouté."
REMOVED_MESSAGE = "Saisies retirées."
FAILED_MESSAGE = "Non enregistré (voir le journal)."
BUTTON_WIDTH = 120
SUGGESTION_HEIGHT = 26
SUGGESTION_COLOR = "#3a3a3a"
IGNORED_KEYS = ("Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Left", "Right", "Up", "Down")

SearchItems = Callable[[str], list[tuple[int, str]]]


def parse_count(text: str) -> int | None:
    """A strictly positive whole number typed with optional spaces; None when unreadable."""
    cleaned = "".join(text.split())
    return int(cleaned) if cleaned.isdigit() and int(cleaned) > 0 else None


class PetManualForm(customtkinter.CTkFrame):
    """Search an item by name, type how many resources and how much XP they gave, then add or remove."""

    def __init__(self, parent: tkinter.Misc, search: SearchItems, on_add: Callable[[int, int, int], bool],
                 on_remove: Callable[[int], bool]) -> None:
        super().__init__(parent, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        self._search, self._on_add, self._on_remove = search, on_add, on_remove
        self._choices: dict[str, int] = {}
        self._names: list[str] = []
        make_label(self, FORM_TITLE, bold=True, anchor="w").pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.item_box = customtkinter.CTkEntry(self, placeholder_text=ITEM_PLACEHOLDER)
        self.item_box.pack(fill="x", padx=PADDING)
        self.item_box.bind("<KeyRelease>", self._key_released)
        self.suggestions = customtkinter.CTkFrame(self, fg_color="transparent", height=0)
        self.units_entry = customtkinter.CTkEntry(self, placeholder_text=UNITS_PLACEHOLDER)
        self.units_entry.pack(fill="x", padx=PADDING, pady=SMALL_PADDING)
        self.experience_entry = customtkinter.CTkEntry(self, placeholder_text=EXPERIENCE_PLACEHOLDER)
        self.experience_entry.pack(fill="x", padx=PADDING)
        self._build_buttons()

    def _build_buttons(self) -> None:
        row = customtkinter.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=PADDING, pady=SMALL_PADDING)
        make_button(row, ADD_TEXT, self.add, BUTTON_WIDTH).pack(side="left")
        make_button(row, REMOVE_TEXT, self.remove, BUTTON_WIDTH).pack(side="left", padx=SMALL_PADDING)
        self.message_label = make_label(self, "", color=MUTED_COLOR, anchor="w", justify="left")
        self.message_label.pack(fill="x", padx=PADDING, pady=(0, PADDING))

    def _key_released(self, event: tkinter.Event) -> None:
        if event.keysym == "Return" and self._names:
            self.choose(self._names[0])
        elif event.keysym == "Escape":
            self.update_choices(clear=True)
        elif event.keysym not in IGNORED_KEYS:
            self.update_choices()

    def update_choices(self, clear: bool = False) -> None:
        """Show, under the field, the items matching the typed text; a click (or Enter) picks one."""
        matches = [] if clear else self._search(self.item_box.get())
        self._choices.update({name: item_id for item_id, name in matches})
        self._names = [name for _, name in matches]
        for child in self.suggestions.winfo_children():
            child.destroy()
        self._place_suggestions()
        for name in self._names:
            customtkinter.CTkButton(self.suggestions, text=name, anchor="w", height=SUGGESTION_HEIGHT,
                                    fg_color=SUGGESTION_COLOR, hover_color=ACCENT_COLOR, corner_radius=CORNER_RADIUS,
                                    command=lambda picked=name: self.choose(picked)).pack(fill="x", pady=1)

    def _place_suggestions(self) -> None:
        """The list takes room only while it has suggestions (an emptied frame would keep its last height)."""
        if self._names:
            self.suggestions.pack(fill="x", padx=PADDING, before=self.units_entry)
        else:
            self.suggestions.pack_forget()

    def choose(self, name: str) -> None:
        """Put the picked name in the field and close the suggestions."""
        self.item_box.delete(0, "end")
        self.item_box.insert(0, name)
        self.update_choices(clear=True)

    def prefill(self, item_id: int, name: str) -> None:
        """Put an item (e.g. the selected table row) in the search box."""
        self._choices[name] = item_id
        self.item_box.delete(0, "end")
        self.item_box.insert(0, name)
        self.update_choices(clear=True)

    def _show(self, text: str, success: bool = False) -> None:
        self.message_label.configure(text=text, text_color=SUCCESS_COLOR if success else ERROR_COLOR)

    def add(self) -> None:
        """Add the typed experience to the chosen resource."""
        item_id, units, experience = self._choices.get(self.item_box.get()), parse_count(self.units_entry.get()), \
            parse_count(self.experience_entry.get())
        if item_id is None:
            self._show(UNKNOWN_ITEM_MESSAGE)
        elif units is None or experience is None:
            self._show(BAD_NUMBER_MESSAGE)
        else:
            saved = self._on_add(item_id, units, experience)
            self._show(ADDED_MESSAGE if saved else FAILED_MESSAGE, saved)

    def remove(self) -> None:
        """Forget what was typed for the chosen resource."""
        item_id = self._choices.get(self.item_box.get())
        if item_id is None:
            self._show(UNKNOWN_ITEM_MESSAGE)
            return
        removed = self._on_remove(item_id)
        self._show(REMOVED_MESSAGE if removed else FAILED_MESSAGE, removed)
