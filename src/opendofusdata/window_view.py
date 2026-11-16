"""The player window: a side menu with the capture status, and five pages filling the rest."""

import logging

import customtkinter

from opendofusdata.app_links import APP_NAME
from opendofusdata.capture_session import CaptureStatus
from opendofusdata.run_pipeline import utc_now
from opendofusdata.ui_theme import (
    ACCENT_COLOR, APPEARANCE_MODE, BUTTON_HEIGHT, COLOR_THEME, COMPACT_BREAKPOINT, CORNER_RADIUS, DEFAULT_HEIGHT,
    DEFAULT_WIDTH, MENU_BUTTON_WIDTH, MENU_TITLE_SIZE, MIN_HEIGHT, MIN_WIDTH, PADDING, SELECTED_COLOR,
    SIDEBAR_COLOR, SIDEBAR_WIDTH, SMALL_PADDING, TEXT_COLOR, TRANSPARENT, WINDOW_COLOR,
)
from opendofusdata.ui_widgets import Page, make_button, make_label
from opendofusdata.window_context import WindowContext
from opendofusdata.window_format import button_enabled, button_label
from opendofusdata.window_status import StatusBlock
from opendofusdata.window_pages import PAGE_NAMES, SETTINGS_PAGE, build_pages

logger = logging.getLogger(__name__)

REFRESH_MILLISECONDS = 500
CLOSE_POLL_MILLISECONDS = 100
UPDATE_BADGE = "  ●"  # the notification sign shown after the menu entry when an update exists
SCREEN_MARGIN = 80
MENU_SIDE = "side"
MENU_TOP = "top"
__all__ = ["CaptureWindow", "PAGE_NAMES"]


class CaptureWindow:
    """Menu + status block + pages; reads session snapshots, never touches the capture thread."""

    def __init__(self, root: customtkinter.CTk, context: WindowContext) -> None:
        self._root, self._context = root, context
        self._closing = False
        self.menu_mode = ""
        context.restart_capture = self.restart_capture
        self._configure_root()
        self.menu_buttons: dict[str, customtkinter.CTkButton] = {}
        self.content = customtkinter.CTkFrame(root, fg_color=WINDOW_COLOR, corner_radius=0)
        self.pages: dict[str, Page] = build_pages(self.content, context)
        self._build_menu()
        self.current_page = PAGE_NAMES[0]
        self.relayout(DEFAULT_WIDTH)
        root.bind("<Configure>", lambda event: self._root_resized(event.widget, event.width))
        self.show_page(self.current_page)

    def _configure_root(self) -> None:
        customtkinter.set_appearance_mode(APPEARANCE_MODE)
        customtkinter.set_default_color_theme(COLOR_THEME)
        self._root.title(APP_NAME)
        self._root.minsize(MIN_WIDTH, MIN_HEIGHT)
        width = min(DEFAULT_WIDTH, max(MIN_WIDTH, self._root.winfo_screenwidth() - SCREEN_MARGIN))
        height = min(DEFAULT_HEIGHT, max(MIN_HEIGHT, self._root.winfo_screenheight() - SCREEN_MARGIN))
        self._root.geometry(f"{width}x{height}")
        self._root.protocol("WM_DELETE_WINDOW", self.close)
        self._root.grid_columnconfigure(1, weight=1)
        self._root.grid_rowconfigure(1, weight=1)

    def _build_menu(self) -> None:
        self.menu = customtkinter.CTkFrame(self._root, width=SIDEBAR_WIDTH, fg_color=SIDEBAR_COLOR, corner_radius=0)
        self.title_label = make_label(self.menu, APP_NAME, MENU_TITLE_SIZE, bold=True)
        for name in self.pages:  # the pages come in menu order, Administration last when configured
            self.menu_buttons[name] = self._menu_button(name)
        self.status_frame = StatusBlock(self.menu)
        self.toggle_button = make_button(self.menu, "", self._toggle_capture, MENU_BUTTON_WIDTH)

    def _menu_button(self, name: str) -> customtkinter.CTkButton:
        return customtkinter.CTkButton(
            self.menu, text=name, anchor="w", width=MENU_BUTTON_WIDTH, height=BUTTON_HEIGHT,
            corner_radius=CORNER_RADIUS, fg_color=TRANSPARENT, text_color=TEXT_COLOR,
            hover_color=SELECTED_COLOR, command=lambda: self.show_page(name))

    def relayout(self, width: int) -> None:
        """Menu on the left, or as a top bar when the window is narrower than COMPACT_BREAKPOINT."""
        mode = MENU_TOP if width < COMPACT_BREAKPOINT else MENU_SIDE
        if mode == self.menu_mode:
            return
        self.menu_mode = mode
        for widget in (self.title_label, *self.menu_buttons.values(), self.status_frame, self.toggle_button):
            widget.pack_forget()
        if mode == MENU_SIDE:
            self._place_side()
        else:
            self._place_top()

    def _place_side(self) -> None:
        self.menu.grid(row=0, column=0, rowspan=2, columnspan=1, sticky="ns")
        self.content.grid(row=0, column=1, rowspan=2, columnspan=1, sticky="nsew")
        self.menu.pack_propagate(False)
        self.title_label.pack(pady=PADDING)
        for button in self.menu_buttons.values():
            button.pack(padx=PADDING, pady=(0, SMALL_PADDING))
        self.toggle_button.pack(side="bottom", pady=PADDING)
        self.status_frame.pack(side="bottom", fill="x", padx=PADDING)

    def _place_top(self) -> None:
        self.menu.grid(row=0, column=0, rowspan=1, columnspan=2, sticky="ew")
        self.content.grid(row=1, column=0, rowspan=1, columnspan=2, sticky="nsew")
        self.menu.pack_propagate(True)
        for button in self.menu_buttons.values():
            button.pack(side="left", padx=SMALL_PADDING, pady=SMALL_PADDING)
        self.toggle_button.pack(side="right", padx=PADDING)

    def _root_resized(self, widget: object, width: int) -> None:
        if widget is self._root:
            self.relayout(width)

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
        """Start the capture, the update check and the periodic refresh."""
        self._context.session.start()
        self._context.updates.start_check()
        self._poll()

    def _poll(self) -> None:
        try:
            self.render()
        except Exception:  # keep refreshing whatever happens to one render
            logger.exception("window refresh failed")
        finally:
            self._root.after(REFRESH_MILLISECONDS, self._poll)

    def render(self) -> None:
        """Show the session state in the menu and refresh the visible page only."""
        snapshot = self._context.session.snapshot()
        self.toggle_button.configure(text=button_label(snapshot),
                                    state="normal" if button_enabled(snapshot) else "disabled")
        self.status_frame.render(snapshot, utc_now())
        self.pages[self.current_page].render(snapshot)
        self._update_badge()
        if self._context.updates.take_restart_request():
            self.close()

    def _update_badge(self) -> None:
        """Show the notification sign on the Réglages entry while a newer version exists."""
        available = self._context.updates.available() is not None
        self.menu_buttons[SETTINGS_PAGE].configure(
            text=SETTINGS_PAGE + (UPDATE_BADGE if available else ""),
            text_color=ACCENT_COLOR if available else TEXT_COLOR)

    def restart_capture(self) -> None:
        """Stop the running capture and start it again (to apply a new server or database)."""
        self._context.session.request_stop()
        self._start_when_stopped()

    def _start_when_stopped(self) -> None:
        if self._context.session.snapshot().status is CaptureStatus.STOPPING:
            self._root.after(CLOSE_POLL_MILLISECONDS, self._start_when_stopped)
        else:
            self._context.session.start()

    def _toggle_capture(self) -> None:
        if self._context.session.snapshot().status is CaptureStatus.RUNNING:
            self._context.session.request_stop()
        else:
            self._context.session.start()
        self.render()

    def close(self) -> None:
        """Ask the capture to stop, wait for it without freezing the window, then close."""
        if self._closing:
            return
        self._closing = True
        self._context.session.request_stop()
        self._close_when_stopped()

    def _close_when_stopped(self) -> None:
        if self._context.session.snapshot().status is CaptureStatus.STOPPING:
            self._root.after(CLOSE_POLL_MILLISECONDS, self._close_when_stopped)
        else:
            self._root.destroy()
