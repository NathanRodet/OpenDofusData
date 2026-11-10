"""Layering test: the pure decoders must not pull in the SQLite storage layer."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE_DIRECTORY = Path(__file__).resolve().parent.parent / "src"
# -I ignores PYTHONPATH, so the script extends sys.path itself from the first argument.
CHECK_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "import dofus_prices.hdv, dofus_prices.market_stats, dofus_prices.export; "
    "sys.exit(1 if 'sqlite3' in sys.modules else 0)"
)


def test_pure_modules_do_not_import_sqlite() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", CHECK_SCRIPT, str(SOURCE_DIRECTORY)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


NAMES_CHECK_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "import dofus_prices.item_names, dofus_prices.names_build; "
    "banned = {'sqlite3', 'scapy', 'urllib.request'}; "
    "sys.exit(1 if banned & set(sys.modules) else 0)"
)


def test_name_index_modules_do_not_import_network_storage_or_capture() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", NAMES_CHECK_SCRIPT, str(SOURCE_DIRECTORY)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


GUARDED_MODULES = (
    "capture", "capture_errors", "tcp", "framing", "protobuf", "hdv", "market_stats", "records",
    "storage", "run_pipeline", "commands", "export", "verbose_table", "timeutil", "discovery",
)
FORBIDDEN_IMPORTS = ("dofus_prices.names_fetch", "dofus_prices.names_build",
                     "dofus_prices.item_names", "dofus_prices.game_servers",
                     "dofus_prices.servers_fetch", "dofus_prices.servers_build",
                     "dofus_prices.servers_commands", "dofus_prices.app_config",
                     "dofus_prices.server_choice", "dofus_prices.server_choice_commands",
                     "urllib")


def forbidden_imports(source: str) -> list[str]:
    """Return the forbidden modules imported by a source text (import and from-import)."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
        found += [name for name in names
                  if any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN_IMPORTS)]
    return found


def test_guard_detects_offending_sources() -> None:
    assert forbidden_imports("import urllib.request") == ["urllib.request"]
    assert forbidden_imports("from dofus_prices import item_names") == ["dofus_prices.item_names"]
    assert forbidden_imports("from urllib import parse") != []
    assert forbidden_imports("from dofus_prices.names_build import write_items_csv") != []
    assert forbidden_imports("import json; from dofus_prices.hdv import decode_lot_prices") == []


@pytest.mark.parametrize("module", GUARDED_MODULES)
def test_capture_decoder_and_storage_modules_stay_offline(module: str) -> None:
    source = (SOURCE_DIRECTORY / "dofus_prices" / f"{module}.py").read_text(encoding="utf-8")
    assert forbidden_imports(source) == []


SERVERS_CHECK_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "import dofus_prices.game_servers, dofus_prices.servers_build; "
    "banned = {'sqlite3', 'scapy', 'urllib.request'}; "
    "sys.exit(1 if banned & set(sys.modules) else 0)"
)


def test_server_list_modules_stay_out_of_the_capture_path() -> None:
    assert forbidden_imports("from dofus_prices.servers_fetch import x") != []
    assert forbidden_imports("from dofus_prices import game_servers") != []
    assert forbidden_imports("import dofus_prices.servers_commands") != []
    assert forbidden_imports("from dofus_prices.servers_build import x") != []
    assert forbidden_imports("from dofus_prices.app_config import load_config") != []
    assert forbidden_imports("import dofus_prices.server_choice") != []
    assert forbidden_imports("from dofus_prices import server_choice_commands") != []


def test_pure_server_modules_do_not_import_network_storage_or_capture() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", SERVERS_CHECK_SCRIPT, str(SOURCE_DIRECTORY)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
