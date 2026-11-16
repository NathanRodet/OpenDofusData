"""The automatic purge setting (off by default; anything but a real boolean counts as off)."""

from opendofusdata.purge_options import PURGE_KEY, config_with_purge, purge_enabled


def test_key_name() -> None:
    assert PURGE_KEY == "purge_old_data"


def test_option_defaults_to_off() -> None:
    assert purge_enabled({}) is False


def test_non_boolean_value_counts_as_off() -> None:
    for value in ("true", 1, None, [True]):
        assert purge_enabled({PURGE_KEY: value}) is False


def test_config_with_purge_roundtrip_and_keeps_other_settings() -> None:
    config = config_with_purge({"other": 1}, True)
    assert config == {"other": 1, PURGE_KEY: True} and purge_enabled(config)
    assert purge_enabled(config_with_purge(config, False)) is False
