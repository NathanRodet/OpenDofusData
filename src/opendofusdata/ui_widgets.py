"""Small CustomTkinter widget factories shared by the pages (the only place styles are applied)."""

from collections.abc import Callable
from typing import Protocol

import customtkinter

from opendofusdata.capture_session import SessionSnapshot
from opendofusdata.ui_theme import (
    ACCENT_COLOR, ACCENT_HOVER_COLOR, BODY_SIZE, BUTTON_HEIGHT, CORNER_RADIUS,
    CARD_TITLE_SIZE, PAGE_BUTTON_WIDTH, TEXT_COLOR,
)


class Page(Protocol):
    """What the window needs from a page: its frame and a way to refresh it."""

    frame: customtkinter.CTkFrame

    def render(self, snapshot: SessionSnapshot) -> None: ...


def make_label(
    parent: customtkinter.CTkBaseClass, text: str = "", size: int = BODY_SIZE, bold: bool = False,
    color: str = TEXT_COLOR, **options: object,
) -> customtkinter.CTkLabel:
    """A label with the window font; extra options go to CTkLabel."""
    font = customtkinter.CTkFont(size=size, weight="bold" if bold else "normal")
    return customtkinter.CTkLabel(parent, text=text, font=font, text_color=color, **options)


CARD_TITLE_WRAP = 300  # inside a detail panel of DETAIL_WIDTH, next to its scrollbar and margins


def make_card_title(parent: customtkinter.CTkBaseClass, text: str) -> customtkinter.CTkLabel:
    """The bold title of a card or of a section of a detail panel (long titles wrap instead of being cut)."""
    return make_label(parent, text, CARD_TITLE_SIZE, bold=True, anchor="w", justify="left",
                      wraplength=CARD_TITLE_WRAP)


def make_button(
    parent: customtkinter.CTkBaseClass, text: str, command: Callable[[], None],
    width: int = PAGE_BUTTON_WIDTH, height: int = BUTTON_HEIGHT,
) -> customtkinter.CTkButton:
    """An accent button of fixed size."""
    return customtkinter.CTkButton(
        parent, text=text, command=command, width=width, height=height,
        corner_radius=CORNER_RADIUS, fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER_COLOR)
