"""What the player window needs from the application (one small shared dataclass)."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from opendofusdata.capture_session import CaptureSession
from opendofusdata.log_feed import NameLookup


@dataclass
class WindowContext:
    """The session, the opener, the config file, the selectable servers and the name lookup."""

    session: CaptureSession
    open_online: Callable[[], None]
    config_path: Path
    server_names: list[str]
    name_of: NameLookup
