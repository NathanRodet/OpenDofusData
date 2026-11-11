"""Tests for the envelope handler feeding the store writer."""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from opendofusdata.framing import Envelope
from opendofusdata.hdv import decode_lot_prices
from opendofusdata.market_stats import decode_market_stats
from opendofusdata.run_pipeline import make_envelope_handler
from opendofusdata.verbose_table import format_lot_prices, format_market_stats
from opendofusdata.storage import PriceStore, StoreWriter
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


def make_echo_handler(tmp_path: Path, echo) -> tuple:
    submitted: list[object] = []

    class RecordingWriter:
        def submit(self, record: object) -> None:
            submitted.append(record)

    return make_envelope_handler(RecordingWriter(), "unknown", lambda: CAPTURE_MOMENT, echo=echo), submitted


def test_echo_receives_one_lots_block_for_a_lot_envelope(tmp_path: Path) -> None:
    blocks: list[str] = []
    handler, _ = make_echo_handler(tmp_path, blocks.append)
    handler(lot_envelope(), FLOW_KEY)
    expected = format_lot_prices(decode_lot_prices(lot_envelope(), "unknown", CAPTURED_AT)) + "\n"
    assert blocks == [expected]


def test_echo_receives_one_stats_block_for_a_stats_envelope(tmp_path: Path) -> None:
    blocks: list[str] = []
    handler, _ = make_echo_handler(tmp_path, blocks.append)
    handler(stats_envelope(), FLOW_KEY)
    expected = format_market_stats(decode_market_stats(stats_envelope(), "unknown", CAPTURED_AT)) + "\n"
    assert blocks == [expected]


def test_echo_is_not_called_for_unrelated_envelopes(tmp_path: Path) -> None:
    blocks: list[str] = []
    handler, _ = make_echo_handler(tmp_path, blocks.append)
    handler(Envelope("other", b""), FLOW_KEY)
    assert blocks == []


def test_handler_without_echo_still_submits(tmp_path: Path) -> None:
    handler, submitted = make_echo_handler(tmp_path, None)
    handler(lot_envelope(), FLOW_KEY)
    assert len(submitted) == 4


def test_failing_echo_warns_once_and_stops_echoing(tmp_path: Path, caplog) -> None:
    calls: list[str] = []

    def broken_echo(text: str) -> None:
        calls.append(text)
        raise OSError("console closed")

    handler, submitted = make_echo_handler(tmp_path, broken_echo)
    handler(lot_envelope(), FLOW_KEY)
    handler(stats_envelope(), FLOW_KEY)
    handler(lot_envelope(), FLOW_KEY)
    assert len(calls) == 1
    assert len(submitted) == 4 + 1 + 4
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1


def test_echo_unicode_error_warns_once_and_keeps_capturing(tmp_path: Path, caplog) -> None:
    calls: list[str] = []

    def ascii_console(text: str) -> None:
        calls.append(text)
        raise UnicodeEncodeError("ascii", "é", 0, 1, "x")

    handler, submitted = make_echo_handler(tmp_path, ascii_console)
    handler(stats_envelope(), FLOW_KEY)
    handler(lot_envelope(), FLOW_KEY)
    assert len(calls) == 1
    assert len(submitted) == 1 + 4
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1
