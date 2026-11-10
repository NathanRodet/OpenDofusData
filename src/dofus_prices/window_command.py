"""The window command: server resolution, then the capture window."""

import argparse
import tkinter
import webbrowser

from dofus_prices.app_links import SAAS_URL
from dofus_prices.capture_errors import EXIT_OK, fail
from dofus_prices.capture_session import CaptureSession
from dofus_prices.capture_stoppable import StoppableCapture, run_stoppable_capture
from dofus_prices.run_pipeline import Clock, utc_now
from dofus_prices.server_choice_commands import resolve_run_server
from dofus_prices.window_view import CaptureWindow

NO_DISPLAY_MESSAGE = "Impossible d'ouvrir la fenêtre ({error})."


def add_window_command(commands: argparse._SubParsersAction, default_database: str) -> None:
    """Register the window command."""
    parser = commands.add_parser("window", help="ouvre la fenêtre de capture des prix de l'HDV")
    parser.add_argument("--db", default=default_database, help="base SQLite (défaut : prices.db)")
    parser.add_argument("--interface", default=None, help="interface réseau à écouter")
    parser.add_argument("--server", default=None, help="nom du serveur de jeu (sans mémorisation)")
    parser.add_argument("--choose-server", action="store_true",
                        help="redemande le serveur même si un serveur est mémorisé")


def _open_online_prices() -> None:
    webbrowser.open(SAAS_URL)


def window_command(
    arguments: argparse.Namespace, capture: StoppableCapture = run_stoppable_capture,
    now: Clock = utc_now,
) -> int:
    """Resolve the server in the console (first-run prompt), then run the window."""
    resolve_run_server(arguments)
    session = CaptureSession(arguments.db, arguments.server, arguments.interface, capture, now)
    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        return fail(NO_DISPLAY_MESSAGE.format(error=error))
    CaptureWindow(root, session, _open_online_prices).start()
    root.mainloop()
    session.stop()
    return EXIT_OK
