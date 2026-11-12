"""What the player window needs from the application (one small shared dataclass)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from opendofusdata.capture_session import CaptureSession
from opendofusdata.log_feed import NameLookup
from opendofusdata.names_refresh import default_data_directory
from opendofusdata.update_controller import UpdateController


@dataclass
class WindowContext:
    """The session, the opener, the config file, the selectable servers and the name lookup.

    `restart_capture` is filled in by the window; `updates` and `data_directory` have
    harmless defaults so a context can be built with the first five fields only.
    """

    session: CaptureSession
    open_online: Callable[[], None]
    config_path: Path
    server_names: list[str]
    name_of: NameLookup
    updates: UpdateController = field(default_factory=UpdateController.inert)
    data_directory: Path = field(default_factory=default_data_directory)
    restart_capture: Callable[[], None] = field(default=lambda: None)
