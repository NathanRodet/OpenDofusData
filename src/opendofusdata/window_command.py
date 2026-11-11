"""The window command: server resolution, then the player window (GUI loaded lazily)."""

import argparse
import webbrowser
from collections.abc import Callable

from opendofusdata import __version__
from opendofusdata.app_config import default_config_path, load_config
from opendofusdata.app_links import SAAS_URL
from opendofusdata.capture_errors import EXIT_OK, fail
from opendofusdata.capture_session import CaptureSession
from opendofusdata.capture_stoppable import StoppableCapture, run_stoppable_capture
from opendofusdata.categories import categories_from_config
from opendofusdata.client_settings import choose_database_path, server_names, update_check_enabled
from opendofusdata.item_labels import item_labeler_for_database
from opendofusdata.names_fetch import http_get_json
from opendofusdata.run_pipeline import Clock, utc_now
from opendofusdata.server_choice_commands import resolve_run_server
from opendofusdata.update_apply import can_self_update
from opendofusdata.update_controller import UpdateController, check_for_update
from opendofusdata.update_install import install_update
from opendofusdata.window_context import WindowContext

NO_DISPLAY_MESSAGE = "Impossible d'ouvrir la fenêtre ({error})."


def add_window_command(commands: argparse._SubParsersAction, default_database: str) -> None:
    """Register the window command."""
    parser = commands.add_parser("window", help="ouvre la fenêtre OpenDofusData")
    parser.add_argument("--db", default=None,
                        help=f"base SQLite (défaut : celle des réglages, sinon {default_database})")
    parser.add_argument("--interface", default=None, help="interface réseau à écouter")
    parser.add_argument("--server", default=None, help="nom du serveur de jeu (sans mémorisation)")
    parser.add_argument("--choose-server", action="store_true",
                        help="redemande le serveur même si un serveur est mémorisé")


def open_online_prices() -> None:
    """Open the online price site in the default browser."""
    webbrowser.open(SAAS_URL)


def _display_error() -> type[Exception]:
    """The exception tkinter raises when no display is available."""
    import tkinter

    return tkinter.TclError


def show_window(context: WindowContext) -> int:
    """Build the window, run it until closed, and always stop the session afterwards."""
    import customtkinter

    from opendofusdata.window_view import CaptureWindow

    try:
        root = customtkinter.CTk()
    except _display_error() as error:
        return fail(NO_DISPLAY_MESSAGE.format(error=error))
    CaptureWindow(root, context).start()
    root.mainloop()
    context.session.stop()
    return EXIT_OK


def build_update_controller(config: dict[str, object]) -> UpdateController:
    """The update controller: checks GitHub at startup unless the player turned it off."""
    return UpdateController(__version__, update_check_enabled(config),
                            lambda: check_for_update(__version__, http_get_json),
                            install_update, can_self_update())


def window_command(
    arguments: argparse.Namespace, capture: StoppableCapture = run_stoppable_capture,
    now: Clock = utc_now,
) -> int:
    """Resolve the server in the console (first-run prompt), then run the window."""
    resolve_run_server(arguments)
    config_path = default_config_path()
    config = load_config(config_path)
    database = choose_database_path(arguments.db, config)
    session = CaptureSession(database, arguments.server, arguments.interface, capture, now,
                             categories=categories_from_config(config))
    return show_window(WindowContext(session, open_online_prices, config_path, server_names(),
                                     item_labeler_for_database(database),
                                     build_update_controller(config)))


WINDOW_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {"window": window_command}
