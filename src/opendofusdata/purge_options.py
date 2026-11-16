"""The automatic local purge setting: off unless the player ticked it."""

from collections.abc import Mapping

PURGE_KEY = "purge_old_data"


def purge_enabled(config: Mapping[str, object]) -> bool:
    """True only for a real boolean `true`; anything else (missing, text, number) counts as off."""
    return config.get(PURGE_KEY) is True


def config_with_purge(config: Mapping[str, object], enabled: bool) -> dict[str, object]:
    """Copy of the config with the automatic purge switched on or off."""
    return {**config, PURGE_KEY: enabled}
