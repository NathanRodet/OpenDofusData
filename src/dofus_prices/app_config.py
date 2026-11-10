"""Persistent user configuration (JSON file): location, tolerant load, atomic save."""

import json
import logging
import os
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_ENV_VAR = "OPENDOFUSDATA_CONFIG"
CONFIG_VERSION = 1
VERSION_KEY = "version"
WINDOWS_PLATFORM = "win32"
WINDOWS_DIRECTORY = "OpenDofusData"
POSIX_DIRECTORY = "opendofusdata"
CONFIG_FILE_NAME = "config.json"
CORRUPT_SUFFIX = ".corrupt"
TEMP_SUFFIX = ".tmp"


def default_config_path(
    environ: Mapping[str, str] = os.environ, platform: str = sys.platform,
    home: Path | None = None,
) -> Path:
    """Return the config file path (environment override, then the per-platform default)."""
    override = environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override)
    home_directory = home if home is not None else Path.home()
    if platform == WINDOWS_PLATFORM:
        roaming = environ.get("APPDATA")
        base = Path(roaming) if roaming else home_directory / "AppData" / "Roaming"
        return base / WINDOWS_DIRECTORY / CONFIG_FILE_NAME
    return home_directory / ".config" / POSIX_DIRECTORY / CONFIG_FILE_NAME


def _parse_config(path: Path) -> dict[str, object] | None:
    """Return the config object, or None when the file cannot be read as a JSON object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as error:
        logger.warning("config illisible (%s : %s), ignorée", path, error)
        return None
    if not isinstance(data, dict):
        logger.warning("config invalide (%s : objet JSON attendu), ignorée", path)
        return None
    return data


def load_config(path: str | Path) -> dict[str, object]:
    """Load the config; a missing, unreadable or invalid file gives {} (never raises)."""
    file_path = Path(path)
    if not file_path.is_file():
        return {}
    return _parse_config(file_path) or {}


def _back_up_corrupt_file(path: Path) -> None:
    """Move a present but invalid config aside (one backup kept) before it is replaced."""
    if path.is_file() and _parse_config(path) is None:
        backup = path.with_name(path.name + CORRUPT_SUFFIX)
        os.replace(path, backup)
        logger.warning("ancienne config conservée dans %s", backup)


def _write_atomically(path: Path, text: str) -> None:
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, suffix=TEMP_SUFFIX)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(text)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def save_config(path: str | Path, config: Mapping[str, object]) -> None:
    """Write the config atomically (UTF-8 JSON), backing up a corrupt file first."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    document = {**config, VERSION_KEY: CONFIG_VERSION}
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    _back_up_corrupt_file(file_path)
    _write_atomically(file_path, text)
