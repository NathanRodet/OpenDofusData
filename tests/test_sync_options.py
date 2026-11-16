"""The send and receive settings and the options a synchronisation round runs with."""

from opendofusdata.app_config import save_config
from opendofusdata.sync_engine import SyncOptions
from opendofusdata.sync_key import SYNC_KEY_CONFIG
from opendofusdata.sync_options import (
    SYNC_RECEIVE_KEY, SYNC_SEND_KEY, config_with_sync_receive, config_with_sync_send, load_sync_options,
    sync_receive_enabled, sync_send_enabled,
)

KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"
URL = "https://sync.exemple.fr"


def write_env(tmp_path, text: str = f"SERVER_URL={URL}\n"):
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_keys_are_the_documented_ones() -> None:
    assert (SYNC_SEND_KEY, SYNC_RECEIVE_KEY) == ("sync_send", "sync_receive")


def test_options_default_to_off() -> None:
    assert sync_send_enabled({}) is False
    assert sync_receive_enabled({}) is False


def test_non_boolean_values_count_as_off() -> None:
    for value in ("true", 1, None, [True], "yes"):
        assert sync_send_enabled({SYNC_SEND_KEY: value}) is False
        assert sync_receive_enabled({SYNC_RECEIVE_KEY: value}) is False


def test_config_helpers_roundtrip_and_keep_other_values() -> None:
    config = config_with_sync_receive(config_with_sync_send({"other": 1}, True), True)
    assert config == {"other": 1, SYNC_SEND_KEY: True, SYNC_RECEIVE_KEY: True}
    assert sync_send_enabled(config) and sync_receive_enabled(config)
    assert sync_send_enabled(config_with_sync_send(config, False)) is False


def test_load_options_none_without_key_url_or_both_off(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    env_path = write_env(tmp_path)
    save_config(config_path, {SYNC_SEND_KEY: True})
    assert load_sync_options(config_path, env_path) is None  # no key
    save_config(config_path, {SYNC_KEY_CONFIG: KEY, SYNC_SEND_KEY: True})
    assert load_sync_options(config_path, tmp_path / "absent.env") is None  # no address
    save_config(config_path, {SYNC_KEY_CONFIG: KEY})
    assert load_sync_options(config_path, env_path) is None  # both off


def test_load_options_reads_the_current_config_each_time(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    env_path = write_env(tmp_path)
    save_config(config_path, {SYNC_KEY_CONFIG: KEY, SYNC_SEND_KEY: True})
    assert load_sync_options(config_path, env_path) == SyncOptions(URL, KEY, True, False)
    save_config(config_path, {SYNC_KEY_CONFIG: KEY, SYNC_RECEIVE_KEY: True})
    assert load_sync_options(config_path, env_path) == SyncOptions(URL, KEY, False, True)
