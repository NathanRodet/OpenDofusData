"""The runtime image carries only what the server needs; test tools live in a separate, equally locked file."""

import re
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
PINNED = re.compile(r"(?m)^([A-Za-z0-9_.-]+)==[\w.]+ \\$")
HASH = re.compile(r"--hash=sha256:[0-9a-f]{64}")
DEV_ONLY = {"pytest", "httpx2", "pyyaml", "pluggy", "iniconfig"}


def pinned_names(path: Path) -> set[str]:
    return {name.lower().replace("_", "-") for name in PINNED.findall(path.read_text(encoding="utf-8"))}


def requested_names(path: Path) -> set[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {re.split(r"[<>=!~;\s#]", line.strip(), maxsplit=1)[0].lower() for line in lines
            if line.strip() and not line.startswith(("#", "-"))}


def test_the_runtime_lock_has_the_server_dependencies_and_no_test_tool() -> None:
    names = pinned_names(SERVER_DIR / "requirements.lock")
    assert {"fastapi", "uvicorn"} <= names
    assert not names & DEV_ONLY, names & DEV_ONLY
    assert requested_names(SERVER_DIR / "requirements.txt") == {"fastapi", "uvicorn"}


def test_the_dev_lock_adds_the_test_tools_on_top_of_the_runtime_ones() -> None:
    names = pinned_names(SERVER_DIR / "requirements-dev.lock")
    assert pinned_names(SERVER_DIR / "requirements.lock") <= names
    assert {"pytest", "httpx2", "pyyaml"} <= names
    assert requested_names(SERVER_DIR / "requirements-dev.txt") == {"httpx2", "pytest", "pyyaml"}


def test_every_package_of_both_locks_has_hashes() -> None:
    for name in ("requirements.lock", "requirements-dev.lock"):
        text = (SERVER_DIR / name).read_text(encoding="utf-8")
        assert len(HASH.findall(text)) >= len(PINNED.findall(text)) > 0, name


def test_the_setup_script_installs_the_dev_lock() -> None:
    assert "requirements-dev.lock" in (SERVER_DIR / "dev.ps1").read_text(encoding="utf-8")
