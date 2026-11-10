"""Tests for the envelope handler feeding the store writer."""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dofus_prices.framing import Envelope
from dofus_prices.run_pipeline import make_envelope_handler
from dofus_prices.storage import PriceStore, StoreWriter
from tests.envelopes import FLOW_KEY, STATS_ITEM_ID, lot_envelope, stats_envelope

CAPTURE_MOMENT = datetime(2026, 11, 10, 10, 29, 17, tzinfo=timezone.utc)
CAPTURED_AT = "2026-11-10T10:29:17Z"
PARIS_ZONE = timezone(timedelta(hours=1))


def test_handler_stores_lot_prices_and_market_stats(tmp_path: Path) -> None:
    database = str(tmp_path / "prices.db")
    writer = StoreWriter(database)
    handler = make_envelope_handler(writer, "Ilyzaelle", lambda: CAPTURE_MOMENT.astimezone(PARIS_ZONE))
    handler(lot_envelope(), FLOW_KEY)
    handler(stats_envelope(), FLOW_KEY)
    writer.stop()
    store = PriceStore(database)
    try:
        lots = store.latest_prices(307)
        stats = store.market_stats_history(STATS_ITEM_ID, "24h")
    finally:
        store.close()
    assert [(lot.lot_size, lot.price) for lot in lots] == [(1, 750), (10, 5868), (100, 49993), (1000, 499999)]
    assert {lot.captured_at for lot in lots} == {CAPTURED_AT}
    assert [(row.sold_count, row.captured_at, row.server) for row in stats] == [(2, CAPTURED_AT, "Ilyzaelle")]
    assert handler.submitted_count == 5


def test_handler_ignores_unrelated_envelopes(tmp_path: Path) -> None:
    writer = StoreWriter(str(tmp_path / "prices.db"))
    handler = make_envelope_handler(writer, "unknown", lambda: CAPTURE_MOMENT)
    handler(Envelope("other", b"\x08\x01"), FLOW_KEY)
    writer.stop()
    assert handler.submitted_count == 0


def test_handler_logs_item_and_lot_price_count(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.INFO)
    writer = StoreWriter(str(tmp_path / "prices.db"))
    make_envelope_handler(writer, "unknown", lambda: CAPTURE_MOMENT)(lot_envelope(), FLOW_KEY)
    writer.stop()
    assert "item 307: 4 lot prices" in caplog.text


def test_handler_logs_item_and_market_periods(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.INFO)
    writer = StoreWriter(str(tmp_path / "prices.db"))
    make_envelope_handler(writer, "unknown", lambda: CAPTURE_MOMENT)(stats_envelope(), FLOW_KEY)
    writer.stop()
    assert f"item {STATS_ITEM_ID}: 1 market periods (24h)" in caplog.text


def test_handler_logs_nothing_for_unrelated_envelopes(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.INFO)
    writer = StoreWriter(str(tmp_path / "prices.db"))
    make_envelope_handler(writer, "unknown", lambda: CAPTURE_MOMENT)(Envelope("other", b"\x08\x01"), FLOW_KEY)
    writer.stop()
    assert caplog.text == ""
