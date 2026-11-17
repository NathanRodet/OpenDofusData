"""The server address of the synchronisation: saved in the settings, else the .env, else the built-in default."""

import json

import pytest

from opendofusdata import sync_client
from opendofusdata.sync_server_url import (
    SERVER_URL_CONFIG, configured_server_url, display_address, origin_from_text, save_server_url,
)

URL = "https://sync.exemple.fr"
OTHER = "https://autre.exemple.fr"


def write_config(tmp_path, **values: object) -> None:
    (tmp_path / "config.json").write_text(json.dumps(values), encoding="utf-8")


def test_nothing_is_configured_by_default(tmp_path) -> None:
    assert configured_server_url(tmp_path / "config.json", tmp_path / ".env") is None


def test_the_env_file_is_used_when_the_settings_have_no_address(tmp_path) -> None:
    (tmp_path / ".env").write_text(f"SERVER_URL={OTHER}\n", encoding="utf-8")
    assert configured_server_url(tmp_path / "config.json", tmp_path / ".env") == OTHER


def test_the_settings_win_over_the_env_file(tmp_path) -> None:
    (tmp_path / ".env").write_text(f"SERVER_URL={OTHER}\n", encoding="utf-8")
    write_config(tmp_path, **{SERVER_URL_CONFIG: URL})
    assert configured_server_url(tmp_path / "config.json", tmp_path / ".env") == URL


def test_the_built_in_default_is_the_last_resort(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_client, "DEFAULT_SERVER_URL", URL)
    assert configured_server_url(tmp_path / "config.json", tmp_path / ".env") == URL


def test_an_invalid_saved_address_is_ignored(tmp_path) -> None:
    write_config(tmp_path, **{SERVER_URL_CONFIG: "http://pas-securise.fr"})
    assert configured_server_url(tmp_path / "config.json", tmp_path / ".env") is None


def test_saving_stores_the_address_in_canonical_form_and_keeps_the_other_settings(tmp_path) -> None:
    write_config(tmp_path, server="Brial")
    assert save_server_url(tmp_path / "config.json", f"  {URL}/  ") is True
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["server"] == "Brial" and saved[SERVER_URL_CONFIG] == URL


@pytest.mark.parametrize("text", ["http://sync.exemple.fr", "sync.exemple.fr/api", "sync.exemple.fr?x=1",
                                  "https://sync.exemple.fr/api", "sync", "-x.fr", "sync..fr",
                                  "https://sync exemple.fr", "ftp://x.fr", "https://"])
def test_a_bad_address_is_refused_and_nothing_is_written(tmp_path, text: str) -> None:
    assert save_server_url(tmp_path / "config.json", text) is False
    assert not (tmp_path / "config.json").exists()


def test_an_empty_address_removes_the_saved_one(tmp_path) -> None:
    write_config(tmp_path, **{SERVER_URL_CONFIG: URL})
    assert save_server_url(tmp_path / "config.json", "") is True
    assert SERVER_URL_CONFIG not in json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("text, origin", [
    ("sync.exemple.fr", URL), ("  Sync.Exemple.fr  ", URL), ("https://sync.exemple.fr/", URL),
    ("sync.exemple.fr:8443", "https://sync.exemple.fr:8443"), ("sync.exemple.fr/", URL),
])
def test_a_bare_domain_gets_https_added(text: str, origin: str) -> None:
    assert origin_from_text(text) == origin


def test_the_domain_is_saved_as_an_https_address(tmp_path) -> None:
    assert save_server_url(tmp_path / "config.json", "sync.exemple.fr") is True
    assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))[SERVER_URL_CONFIG] == URL


def test_the_address_is_shown_as_a_domain_without_https() -> None:
    assert display_address(URL) == "sync.exemple.fr"
    assert display_address("https://sync.exemple.fr:8443") == "sync.exemple.fr:8443"
    assert display_address(None) == ""
