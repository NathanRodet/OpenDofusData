"""Suite-wide isolation: relative default paths never resolve inside the repository."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_working_directory(tmp_path_factory, monkeypatch) -> None:
    """Run every test from an empty temp directory (data/, prices.db, captures/ absent)."""
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
