"""The options of a synchronisation round: a saved key and a server address are all it takes (no send/receive boxes)."""

from opendofusdata.app_config import save_config
from opendofusdata.sync_engine import SyncOptions
from opendofusdata.sync_key import SYNC_KEY_CONFIG
from opendofusdata.sync_options import load_sync_options

KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"
URL = "https://sync.exemple.fr"


def write_env(tmp_path, text: str = f"SERVER_URL={URL}\n"):
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_key_and_an_address_turn_both_directions_on(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    save_config(config_path, {SYNC_KEY_CONFIG: KEY})
    assert load_sync_options(config_path, write_env(tmp_path)) == SyncOptions(URL, KEY, True, True, 60)


def test_nothing_runs_without_a_key_or_without_an_address(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    assert load_sync_options(config_path, write_env(tmp_path)) is None  # no config at all
    save_config(config_path, {SYNC_KEY_CONFIG: KEY})
    assert load_sync_options(config_path, tmp_path / "absent.env") is None  # no address


def test_removing_the_key_stops_the_synchronisation(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    env_path = write_env(tmp_path)
    save_config(config_path, {SYNC_KEY_CONFIG: KEY})
    assert load_sync_options(config_path, env_path) is not None
    save_config(config_path, {})
    assert load_sync_options(config_path, env_path) is None


def test_an_old_send_or_receive_setting_in_the_config_no_longer_matters(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    save_config(config_path, {SYNC_KEY_CONFIG: KEY, "sync_send": False, "sync_receive": False})
    assert load_sync_options(config_path, write_env(tmp_path)) == SyncOptions(URL, KEY, True, True, 60)


def test_a_malformed_key_is_not_used(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    save_config(config_path, {SYNC_KEY_CONFIG: "pas une clé"})
    assert load_sync_options(config_path, write_env(tmp_path)) is None


def test_an_address_saved_in_the_settings_is_used_by_the_worker(tmp_path) -> None:
    import json

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"sync_api_key": KEY, "sync_server_url": "https://reglages.exemple.fr"}),
                           encoding="utf-8")
    options = load_sync_options(config_path, tmp_path / "absent.env")
    assert options == SyncOptions("https://reglages.exemple.fr", KEY, True, True, 60)
