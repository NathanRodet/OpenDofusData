"""Reset of the collected data: a backup of the database, then every collected row removed."""

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

COLLECTED_TABLES = ("lot_prices", "market_stats", "broken_items", "pet_feedings")
BACKUP_TIME_FORMAT = "%Y%m%d-%H%M%S"
MISSING_MESSAGE = "Base de données introuvable : {path}"


def backup_path_for(database_path: Path, now: datetime) -> Path:
    """`<name>-backup-YYYYMMDD-HHMMSS.db`, next to the database."""
    stamp = now.strftime(BACKUP_TIME_FORMAT)
    return database_path.with_name(f"{database_path.stem}-backup-{stamp}{database_path.suffix}")


def _existing_tables(connection: sqlite3.Connection) -> list[str]:
    known = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return [table for table in COLLECTED_TABLES if table in known]


def collected_counts(database_path: str) -> dict[str, int]:
    """The number of rows of each collected table (0 for a table that does not exist)."""
    with closing(sqlite3.connect(database_path)) as connection:
        existing = _existing_tables(connection)
        return {table: (connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if table in existing else 0)
                for table in COLLECTED_TABLES}


def reset_collected_data(database_path: str, now: datetime) -> Path:
    """Back the database up, then delete every collected row (names and servers are kept).

    Raises FileNotFoundError when the database does not exist; returns the backup path.
    """
    source = Path(database_path)
    if not source.is_file():
        raise FileNotFoundError(MISSING_MESSAGE.format(path=database_path))
    backup = backup_path_for(source, now)
    with closing(sqlite3.connect(database_path)) as connection:
        with closing(sqlite3.connect(backup)) as copy:
            connection.backup(copy)
        for table in _existing_tables(connection):
            connection.execute(f"DELETE FROM {table}")
        connection.commit()
        connection.execute("VACUUM")
    return backup
