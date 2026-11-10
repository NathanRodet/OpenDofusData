"""Tests for the persistent user configuration file (temp files only)."""

import json
import logging
import os
from pathlib import Path

import pytest

from dofus_prices.app_config import (CONFIG_ENV_VAR, CONFIG_VERSION, default_config_path,
                                     load_config, save_config)


def test_missing_file_gives_empty_config(tmp_path: Path) -> None:
    assert load_config(tmp_path / "absent.json") == {}


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '"text"', ""])
def test_corrupt_or_non_object_file_gives_empty_config_with_warning(
        tmp_path: Path, caplog, content: str) -> None:
    path = tmp_path / "config.json"
    path.write_text(content, encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert load_config(path) == {}
    assert "config" in caplog.text
    assert path.read_text(encoding="utf-8") == content


def test_binary_garbage_gives_empty_config(tmp_path: Path, caplog) -> None:
    path = tmp_path / "config.json"
    path.write_bytes(b"\xff\xfe\x00\x80")
    with caplog.at_level(logging.WARNING):
        assert load_config(path) == {}


def test_save_creates_directory_and_writes_utf8_with_version(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "dir" / "config.json"
    save_config(path, {"server": "Ménagerie"})
    text = path.read_text(encoding="utf-8")
    assert "Ménagerie" in text
    assert json.loads(text) == {"server": "Ménagerie", "version": CONFIG_VERSION}
    assert load_config(path)["server"] == "Ménagerie"


def test_unknown_keys_are_preserved(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    save_config(path, {"future": [1, 2], "server": "Brial"})
    config = load_config(path)
    config["server"] = "Dakal"
    save_config(path, config)
    assert load_config(path) == {"future": [1, 2], "server": "Dakal", "version": 1}


def test_failed_write_leaves_no_temp_file_and_keeps_old_content(
        tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "config.json"
    save_config(path, {"server": "Brial"})

    def failing_replace(source, destination) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        save_config(path, {"server": "Dakal"})
    assert [item.name for item in tmp_path.iterdir()] == ["config.json"]
    assert load_config(path)["server"] == "Brial"


def test_unserialisable_value_leaves_no_temp_file(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        save_config(tmp_path / "config.json", {"server": object()})
    assert list(tmp_path.iterdir()) == []


def test_corrupt_file_is_backed_up_before_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    save_config(path, {"server": "Brial"})
    assert (tmp_path / "config.json.corrupt").read_text(encoding="utf-8") == "{broken"
    assert load_config(path)["server"] == "Brial"


def test_only_one_backup_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("first", encoding="utf-8")
    save_config(path, {})
    path.write_text("second", encoding="utf-8")
    save_config(path, {})
    assert (tmp_path / "config.json.corrupt").read_text(encoding="utf-8") == "second"
    assert sorted(item.name for item in tmp_path.iterdir()) == ["config.json", "config.json.corrupt"]


def test_valid_file_is_not_backed_up(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    save_config(path, {"server": "A"})
    save_config(path, {"server": "B"})
    assert [item.name for item in tmp_path.iterdir()] == ["config.json"]


def test_env_override_wins(tmp_path: Path) -> None:
    target = str(tmp_path / "custom.json")
    assert default_config_path({CONFIG_ENV_VAR: target}, "win32", tmp_path) == Path(target)


def test_windows_path_uses_appdata() -> None:
    path = default_config_path({"APPDATA": "C:/Users/x/AppData/Roaming"}, "win32", Path("C:/home"))
    assert path == Path("C:/Users/x/AppData/Roaming") / "OpenDofusData" / "config.json"


def test_windows_without_appdata_falls_back_to_home(tmp_path: Path) -> None:
    path = default_config_path({}, "win32", tmp_path)
    assert path == tmp_path / "AppData" / "Roaming" / "OpenDofusData" / "config.json"


def test_other_platforms_use_dot_config(tmp_path: Path) -> None:
    path = default_config_path({}, "linux", tmp_path)
    assert path == tmp_path / ".config" / "opendofusdata" / "config.json"


def test_suite_config_path_is_the_isolated_temp_file() -> None:
    assert default_config_path() == Path(os.environ[CONFIG_ENV_VAR])
