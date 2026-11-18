"""The window command: server resolution, then the player window (GUI loaded lazily)."""

import argparse
import threading
from collections.abc import Callable

from opendofusdata import __version__
from opendofusdata.app_config import default_config_path, load_config
from opendofusdata.capture_errors import EXIT_OK, fail
from opendofusdata.capture_session import CaptureSession
from opendofusdata.capture_stoppable import StoppableCapture, run_stoppable_capture
from opendofusdata.env_file import env_file_path
from opendofusdata.client_settings import (
    choose_database_path, default_database_path, server_names, update_check_enabled,
)
from opendofusdata.item_labels import item_labelers_for_database
from opendofusdata.local_purge import startup_purge
from opendofusdata.names_fetch import http_get_json
from opendofusdata.run_pipeline import Clock, utc_now
from opendofusdata.server_choice_commands import resolve_run_server
from opendofusdata.sync_options import load_sync_options
from opendofusdata.sync_stream import SyncStream
from opendofusdata.sync_worker import SyncWorker
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
    database = choose_database_path(arguments.db, config, default_database_path())
    session = CaptureSession(database, arguments.server, arguments.interface, capture, now)
    name_of, type_of = item_labelers_for_database(database)
    load_options = lambda: load_sync_options(config_path, env_file_path(config_path))  # noqa: E731
    worker = SyncWorker(lambda: session.database_path, load_options)
    stream = SyncStream(load_options, worker.wake)
    context = WindowContext(session, config_path, server_names(), name_of, build_update_controller(config),
                            type_of=type_of, sync_status=worker.status, sync_summary=worker.summary,
                            auto_reference=True)
    threading.Thread(target=startup_purge, args=(config, database), name="startup-purge", daemon=True).start()
    worker.start()
    stream.start()
    try:
        return show_window(context)
    finally:
        stream.stop()
        worker.stop()


WINDOW_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {"window": window_command}
