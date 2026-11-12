"""Tests of the read-only view connection."""

import logging
import sqlite3
from contextlib import closing

import pytest

from opendofusdata.records import LotPrice
from opendofusdata.storage import PriceStore
from opendofusdata.view_connection import open_view_connection


def test_a_missing_file_gives_none_and_a_warning(tmp_path, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        assert open_view_connection(str(tmp_path / "absent.db")) is None
    assert "absent.db" in caplog.text


def test_the_connection_reads_but_cannot_write(tmp_path) -> None:
    path = str(tmp_path / "p.db")
    store = PriceStore(path)
    store.save_lot_price(LotPrice(7, "Brial", 1, 100, "2026-11-12T10:00:00Z"))
    store.close()
    with closing(open_view_connection(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM lot_prices").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM lot_prices")
