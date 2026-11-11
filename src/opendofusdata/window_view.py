"""The player window: dark side menu, five pages, and the Arrêter / Relancer button."""

import logging

import customtkinter

from opendofusdata.app_links import APP_NAME
from opendofusdata.capture_session import CaptureStatus
from opendofusdata.ui_theme import (
    APPEARANCE_MODE, BUTTON_HEIGHT, COLOR_THEME, CORNER_RADIUS, DEFAULT_HEIGHT, DEFAULT_WIDTH,
    MENU_BUTTON_WIDTH, MENU_TITLE_SIZE, MIN_HEIGHT, MIN_WIDTH, PADDING, SELECTED_COLOR, SIDEBAR_COLOR,
    SIDEBAR_WIDTH, SMALL_PADDING,
    TEXT_COLOR, TRANSPARENT, WINDOW_COLOR,
)
from opendofusdata.ui_widgets import Page, make_button, make_label
from opendofusdata.window_context import WindowContext
from opendofusdata.window_format import button_enabled, button_label
from opendofusdata.window_pages import PAGE_NAMES, build_pages

logger = logging.getLogger(__name__)

REFRESH_MILLISECONDS = 500
CLOSE_POLL_MILLISECONDS = 100
__all__ = ["CaptureWindow", "PAGE_NAMES"]


class CaptureWindow:
    """Side menu + pages; reads session snapshots, never touches the capture thread."""

    def __init__(self, root: customtkinter.CTk, context: WindowContext) -> None:
        self._root, self._context = root, context
        self._configure_root()
        self.menu_buttons: dict[str, customtkinter.CTkButton] = {}
        self.toggle_button = self._build_sidebar()
        self.content = customtkinter.CTkFrame(root, fg_color=WINDOW_COLOR, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.pages: dict[str, Page] = build_pages(self.content, context)
        self.current_page = PAGE_NAMES[0]
        self.show_page(self.current_page)

    def _configure_root(self) -> None:
        customtkinter.set_appearance_mode(APPEARANCE_MODE)
        customtkinter.set_default_color_theme(COLOR_THEME)
        self._root.title(APP_NAME)
        self._root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self._root.geometry(f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
        self._root.protocol("WM_DELETE_WINDOW", self.close)
        self._root.grid_columnconfigure(1, weight=1)
        self._root.grid_rowconfigure(0, weight=1)

    def _build_sidebar(self) -> customtkinter.CTkButton:
        sidebar = customtkinter.CTkFrame(self._root, width=SIDEBAR_WIDTH, fg_color=SIDEBAR_COLOR,
                                         corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.pack_propagate(False)
        make_label(sidebar, APP_NAME, MENU_TITLE_SIZE, bold=True).pack(pady=PADDING)
        for name in PAGE_NAMES:
            self.menu_buttons[name] = self._menu_button(sidebar, name)
        toggle = make_button(sidebar, "", self._toggle_capture, MENU_BUTTON_WIDTH)
        toggle.pack(side="bottom", pady=PADDING)
        return toggle

    def _menu_button(self, sidebar: customtkinter.CTkFrame, name: str) -> customtkinter.CTkButton:
        button = customtkinter.CTkButton(
            sidebar, text=name, anchor="w", width=MENU_BUTTON_WIDTH, height=BUTTON_HEIGHT,
            corner_radius=CORNER_RADIUS, fg_color=TRANSPARENT, text_color=TEXT_COLOR,
            hover_color=SELECTED_COLOR, command=lambda: self.show_page(name))
        button.pack(pady=(0, SMALL_PADDING))
        return button

    def show_page(self, name: str) -> None:
        """Display one page and highlight its menu entry."""
        for page_name, page in self.pages.items():
            page.frame.pack_forget()
            selected = page_name == name
            self.menu_buttons[page_name].configure(fg_color=SELECTED_COLOR if selected else TRANSPARENT)
        self.pages[name].frame.pack(fill="both", expand=True)
        self.current_page = name
        self.render()

    def start(self) -> None:
        """Start the capture and the periodic refresh."""
        self._context.session.start()
        self._poll()

    def _poll(self) -> None:
        try:
            self.render()
        except Exception:  # keep refreshing whatever happens to one render
            logger.exception("window refresh failed")
        finally:
            self._root.after(REFRESH_MILLISECONDS, self._poll)

    def render(self) -> None:
        """Show the current session state on the toggle button and the visible page."""
        snapshot = self._context.session.snapshot()
        self.toggle_button.configure(text=button_label(snapshot),
                                    state="normal" if button_enabled(snapshot) else "disabled")
        self.pages[self.current_page].render(snapshot)

    def _toggle_capture(self) -> None:
        if self._context.session.snapshot().status is CaptureStatus.RUNNING:
            self._context.session.request_stop()
        else:
            self._context.session.start()
        self.render()

    def close(self) -> None:
        """Ask the capture to stop, wait for it without freezing the window, then close."""
        self._context.session.request_stop()
        self._close_when_stopped()

    def _close_when_stopped(self) -> None:
        if self._context.session.snapshot().status is CaptureStatus.STOPPING:
            self._root.after(CLOSE_POLL_MILLISECONDS, self._close_when_stopped)
        else:
            self._root.destroy()
