"""Small CustomTkinter widget factories shared by the pages (the only place styles are applied)."""

from collections.abc import Callable
from typing import Protocol

import customtkinter

from opendofusdata.capture_session import SessionSnapshot
from opendofusdata.ui_theme import (
    ACCENT_COLOR, ACCENT_HOVER_COLOR, BODY_SIZE, BUTTON_HEIGHT, CARD_COLOR, CORNER_RADIUS,
    MUTED_COLOR, PADDING, PAGE_BUTTON_WIDTH, PAGE_MAX_WIDTH, SMALL_PADDING, TEXT_COLOR,
    TINY_PADDING, TITLE_SIZE, TRANSPARENT,
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


def make_button(
    parent: customtkinter.CTkBaseClass, text: str, command: Callable[[], None],
    width: int = PAGE_BUTTON_WIDTH,
) -> customtkinter.CTkButton:
    """An accent button of fixed size."""
    return customtkinter.CTkButton(
        parent, text=text, command=command, width=width, height=BUTTON_HEIGHT,
        corner_radius=CORNER_RADIUS, fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER_COLOR)


def make_card(parent: customtkinter.CTkBaseClass) -> customtkinter.CTkFrame:
    """A rounded grey block that spans the page column."""
    card = customtkinter.CTkFrame(parent, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
    card.pack(fill="x", pady=(0, SMALL_PADDING))
    return card


def make_page(
    parent: customtkinter.CTkBaseClass, max_width: int = PAGE_MAX_WIDTH, scrollable: bool = False,
) -> tuple[customtkinter.CTkFrame, customtkinter.CTkFrame]:
    """Return (page frame, centred body column of at most `max_width`, scrolling if asked)."""
    frame = customtkinter.CTkFrame(parent, fg_color=TRANSPARENT, corner_radius=0)
    if scrollable:
        body = customtkinter.CTkScrollableFrame(frame, width=max_width, fg_color=TRANSPARENT)
        body.pack(fill="y", expand=True, padx=PADDING, pady=PADDING)
        return frame, body
    body = customtkinter.CTkFrame(frame, width=max_width, fg_color=TRANSPARENT)
    body.pack_propagate(False)
    body.pack(fill="y", expand=True, padx=PADDING, pady=PADDING)
    return frame, body


def add_title(body: customtkinter.CTkFrame, title: str, subtitle: str = "") -> None:
    """The page title and an optional muted line under it."""
    make_label(body, title, TITLE_SIZE, bold=True, anchor="w").pack(fill="x")
    if subtitle:
        make_label(body, subtitle, color=MUTED_COLOR, anchor="w", justify="left",
                   wraplength=PAGE_MAX_WIDTH).pack(fill="x", pady=(TINY_PADDING, PADDING))
