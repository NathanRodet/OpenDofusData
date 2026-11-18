"""The Réglages row that sets how often the application asks the server for news (10 to 300 seconds)."""

import customtkinter

from opendofusdata.settings_rows import make_row
from opendofusdata.sync_interval import (
    INTERVAL_STEP_SECONDS, MAX_INTERVAL_SECONDS, MIN_INTERVAL_SECONDS, clamp_interval, load_sync_interval,
    save_sync_interval,
)
from opendofusdata.ui_theme import MUTED_COLOR, SMALL_PADDING
from opendofusdata.ui_widgets import make_label
from opendofusdata.window_context import WindowContext

TITLE = "Fréquence de synchronisation"
NOTE = ("Toutes les combien de secondes l'application échange avec le serveur (de 10 à 300, 60 par défaut). "
        "Le serveur prévient aussi tout de suite quand il y a du nouveau.")
VALUE_TEXT = "{seconds} s"
SLIDER_WIDTH = 180
SAVE_FAILED_TEXT = "Non enregistré (voir le fichier de log)."


class SyncIntervalRow:
    """A slider in steps of five seconds; the value is saved when the slider is released."""

    def __init__(self, parent: customtkinter.CTkFrame, context: WindowContext) -> None:
        self._config_path = context.config_path
        row = make_row(parent, TITLE, NOTE)
        steps = (MAX_INTERVAL_SECONDS - MIN_INTERVAL_SECONDS) // INTERVAL_STEP_SECONDS
        self.slider = customtkinter.CTkSlider(row.controls, from_=MIN_INTERVAL_SECONDS, to=MAX_INTERVAL_SECONDS,
                                              number_of_steps=steps, width=SLIDER_WIDTH, command=self._moved)
        self.value_label = make_label(row.controls, "", bold=True)
        self.message_label = make_label(row.body, "", color=MUTED_COLOR, anchor="w")
        self.slider.pack(side="left")
        self.value_label.pack(side="left", padx=(SMALL_PADDING, 0))
        self.slider.set(load_sync_interval(self._config_path))
        self._moved(self.slider.get())
        self.slider.bind("<ButtonRelease-1>", lambda _event: self.save(), add="+")

    def seconds(self) -> int:
        """The value of the slider as a whole number of seconds inside the allowed range."""
        return clamp_interval(round(self.slider.get()))

    def _moved(self, _value: float) -> None:
        self.value_label.configure(text=VALUE_TEXT.format(seconds=self.seconds()))

    def save(self) -> None:
        """Keep the chosen interval; the worker reads it at its next round."""
        saved = save_sync_interval(self._config_path, self.seconds())
        self.message_label.configure(text="" if saved else SAVE_FAILED_TEXT)
        if not saved:
            self.message_label.pack(fill="x")
