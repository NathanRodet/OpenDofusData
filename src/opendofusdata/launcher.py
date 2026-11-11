"""Entry point of the packaged program: opens the window by default and logs to a file."""

import logging
import logging.handlers
import sys
from pathlib import Path

from opendofusdata import cli
from opendofusdata.app_config import default_config_path

LOG_FILE_NAME = "opendofusdata.log"
LOG_MAX_BYTES = 1024 * 1024
LOG_BACKUP_COUNT = 2
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
DEFAULT_COMMAND = "window"
HANDLER_NAME = "opendofusdata-file"


def arguments_for(argv: list[str]) -> list[str]:
    """No argument means a double-click: open the window."""
    return argv or [DEFAULT_COMMAND]


def log_file_path() -> Path:
    """The log file, next to the player's config.json."""
    return default_config_path().parent / LOG_FILE_NAME


def configure_file_logging(path: Path) -> None:
    """Send the logs to a small rotating file (a windowed program has no console); idempotent."""
    root = logging.getLogger()
    if any(handler.get_name() == HANDLER_NAME for handler in root.handlers):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8")
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def main(argv: list[str] | None = None) -> int:
    """Run the program; the file logger is installed first so the CLI keeps it."""
    try:
        configure_file_logging(log_file_path())
    except OSError:  # an unwritable log folder must not prevent the window from opening
        logging.getLogger(__name__).warning("journal de fichier indisponible")
    return cli.main(arguments_for(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
