"""Layering test: the pure decoders must not pull in the SQLite storage layer."""

import subprocess
import sys
from pathlib import Path

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
