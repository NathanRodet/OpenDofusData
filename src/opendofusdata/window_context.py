"""What the player window needs from the application (one small shared dataclass)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from opendofusdata.capture_session import CaptureSession
from opendofusdata.item_labels import UNKNOWN_ITEM_TYPE, item_labelers_for_database
from opendofusdata.log_feed import NameLookup
from opendofusdata.names_refresh import default_data_directory
from opendofusdata.update_controller import UpdateController


@dataclass
class WindowContext:
    """The session, the config file, the selectable servers and the name lookup.

    `restart_capture` is filled in by the window; `updates` and `data_directory` have
    harmless defaults so a context can be built with the first four fields only.
    """

    session: CaptureSession
    config_path: Path
    server_names: list[str]
    name_of: NameLookup
    updates: UpdateController = field(default_factory=UpdateController.inert)
    data_directory: Path = field(default_factory=default_data_directory)
    restart_capture: Callable[[], None] = field(default=lambda: None)
    type_of: NameLookup = field(default=lambda item_id: UNKNOWN_ITEM_TYPE)
    sync_status: Callable[[], str] = field(default=lambda: "")
    reference_generation: int = 0

    def reference_data_changed(self) -> None:
        """Tell the pages that the recipe and effect files were downloaded again."""
        self.reference_generation += 1

    def use_item_names(self, database_path: str) -> None:
        """Read the item names and types of a database (after a download or a database change)."""
        self.name_of, self.type_of = item_labelers_for_database(database_path)
