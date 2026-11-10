"""Suite-wide isolation: relative default paths never resolve inside the repository."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_working_directory(tmp_path_factory, monkeypatch) -> None:
    """Run every test from an empty temp directory (data/, prices.db, captures/ absent)."""
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path_factory, monkeypatch) -> None:
    """Point the user config file at a temp path: the real %APPDATA% is never touched."""
    config_directory = tmp_path_factory.mktemp("config")
    monkeypatch.setenv("OPENDOFUSDATA_CONFIG", str(config_directory / "config.json"))
