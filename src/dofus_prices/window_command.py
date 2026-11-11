"""The window command: server resolution, then the capture window (tkinter loaded lazily)."""

import argparse
import webbrowser
from collections.abc import Callable

from dofus_prices.app_links import SAAS_URL
from dofus_prices.capture_errors import EXIT_OK, fail
from dofus_prices.capture_session import CaptureSession
from dofus_prices.capture_stoppable import StoppableCapture, run_stoppable_capture
from dofus_prices.run_pipeline import Clock, utc_now
from dofus_prices.server_choice_commands import resolve_run_server

NO_DISPLAY_MESSAGE = "Impossible d'ouvrir la fenêtre ({error})."


def add_window_command(commands: argparse._SubParsersAction, default_database: str) -> None:
    """Register the window command."""
    parser = commands.add_parser("window", help="ouvre la fenêtre de capture des prix de l'HDV")
    parser.add_argument("--db", default=default_database, help="base SQLite (défaut : prices.db)")
    parser.add_argument("--interface", default=None, help="interface réseau à écouter")
    parser.add_argument("--server", default=None, help="nom du serveur de jeu (sans mémorisation)")
    parser.add_argument("--choose-server", action="store_true",
                        help="redemande le serveur même si un serveur est mémorisé")


def open_online_prices() -> None:
    """Open the online price site in the default browser."""
    webbrowser.open(SAAS_URL)


def show_window(session: CaptureSession, open_online: Callable[[], None]) -> int:
    """Build the window, run it until closed, and always stop the session afterwards."""
    import tkinter

    from dofus_prices.window_view import CaptureWindow

    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        return fail(NO_DISPLAY_MESSAGE.format(error=error))
    CaptureWindow(root, session, open_online).start()
    root.mainloop()
    session.stop()
    return EXIT_OK


def window_command(
    arguments: argparse.Namespace, capture: StoppableCapture = run_stoppable_capture,
    now: Clock = utc_now,
) -> int:
    """Resolve the server in the console (first-run prompt), then run the window."""
    resolve_run_server(arguments)
    session = CaptureSession(arguments.db, arguments.server, arguments.interface, capture, now)
    return show_window(session, open_online_prices)


WINDOW_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {"window": window_command}
