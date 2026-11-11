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
    "import opendofusdata.hdv, opendofusdata.market_stats, opendofusdata.export; "
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
    "import opendofusdata.item_names, opendofusdata.names_build; "
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
    "capture_stoppable", "capture_session", "session_counters",
)
FORBIDDEN_IMPORTS = ("opendofusdata.names_fetch", "opendofusdata.names_build",
                     "opendofusdata.item_names", "opendofusdata.game_servers",
                     "opendofusdata.servers_fetch", "opendofusdata.servers_build",
                     "opendofusdata.servers_commands", "opendofusdata.app_config",
                     "opendofusdata.server_choice", "opendofusdata.server_choice_commands",
                     "opendofusdata.window_view", "opendofusdata.window_command",
                     "opendofusdata.app_links", "tkinter", "urllib")


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
    assert forbidden_imports("from opendofusdata import item_names") == ["opendofusdata.item_names"]
    assert forbidden_imports("from urllib import parse") != []
    assert forbidden_imports("from opendofusdata.names_build import write_items_csv") != []
    assert forbidden_imports("import json; from opendofusdata.hdv import decode_lot_prices") == []


@pytest.mark.parametrize("module", GUARDED_MODULES)
def test_capture_decoder_and_storage_modules_stay_offline(module: str) -> None:
    source = (SOURCE_DIRECTORY / "opendofusdata" / f"{module}.py").read_text(encoding="utf-8")
    assert forbidden_imports(source) == []


SERVERS_CHECK_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "import opendofusdata.game_servers, opendofusdata.servers_build; "
    "banned = {'sqlite3', 'scapy', 'urllib.request'}; "
    "sys.exit(1 if banned & set(sys.modules) else 0)"
)


def test_server_list_modules_stay_out_of_the_capture_path() -> None:
    assert forbidden_imports("from opendofusdata.servers_fetch import x") != []
    assert forbidden_imports("from opendofusdata import game_servers") != []
    assert forbidden_imports("import opendofusdata.servers_commands") != []
    assert forbidden_imports("from opendofusdata.servers_build import x") != []
    assert forbidden_imports("from opendofusdata.app_config import load_config") != []
    assert forbidden_imports("import opendofusdata.server_choice") != []
    assert forbidden_imports("from opendofusdata import server_choice_commands") != []


def test_pure_server_modules_do_not_import_network_storage_or_capture() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", SERVERS_CHECK_SCRIPT, str(SOURCE_DIRECTORY)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


WINDOW_LOGIC_CHECK_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "import opendofusdata.capture_session, opendofusdata.window_format, opendofusdata.capture_stoppable; "
    "banned = {'tkinter', 'scapy', 'webbrowser'}; "
    "sys.exit(1 if banned & set(sys.modules) else 0)"
)


def test_window_logic_modules_need_no_gui_nor_scapy() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", WINDOW_LOGIC_CHECK_SCRIPT, str(SOURCE_DIRECTORY)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


CLIENT_LOGIC_CHECK_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "import opendofusdata.categories, opendofusdata.log_feed, opendofusdata.client_settings; "
    "banned = {'tkinter', 'customtkinter', 'scapy', 'sqlite3', 'webbrowser'}; "
    "sys.exit(1 if banned & set(sys.modules) else 0)"
)


def test_client_logic_modules_need_no_gui_scapy_nor_sqlite() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", CLIENT_LOGIC_CHECK_SCRIPT, str(SOURCE_DIRECTORY)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
