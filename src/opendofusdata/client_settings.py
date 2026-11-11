"""Persistent client settings kept in config.json: database path and server (pure helpers)."""

from collections.abc import Mapping

from opendofusdata.game_servers import DEFAULT_SERVERS_PATH, available_servers
from opendofusdata.server_choice import SERVER_KEY

DATABASE_KEY = "database_path"
UPDATE_CHECK_KEY = "check_updates"
DEFAULT_DATABASE = "prices.db"


def database_from_config(config: Mapping[str, object]) -> str | None:
    """The saved database path, or None when absent, blank or not a string."""
    saved = config.get(DATABASE_KEY)
    return saved.strip() or None if isinstance(saved, str) else None


def choose_database_path(option: str | None, config: Mapping[str, object]) -> str:
    """Option first, then the saved path, then the default `prices.db`."""
    return option or database_from_config(config) or DEFAULT_DATABASE


def config_with_database(config: Mapping[str, object], path: str) -> dict[str, object]:
    """Copy of the config with the database path set."""
    return {**config, DATABASE_KEY: path}


def config_with_server(config: Mapping[str, object], name: str) -> dict[str, object]:
    """Copy of the config with the remembered server set."""
    return {**config, SERVER_KEY: name}


def update_check_enabled(config: Mapping[str, object]) -> bool:
    """Whether the window checks for a new version at startup (on unless the player turned it off)."""
    saved = config.get(UPDATE_CHECK_KEY)
    return saved if isinstance(saved, bool) else True


def config_with_update_check(config: Mapping[str, object], enabled: bool) -> dict[str, object]:
    """Copy of the config with the startup update check switched on or off."""
    return {**config, UPDATE_CHECK_KEY: enabled}


def server_names() -> list[str]:
    """Names of the selectable game servers, sorted without regard to case."""
    return sorted((server.name for server in available_servers(DEFAULT_SERVERS_PATH)), key=str.casefold)
