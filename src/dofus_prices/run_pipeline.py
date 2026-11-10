"""The run command: decodes captured envelopes and hands records to the store writer."""

import argparse
import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

from dofus_prices.capture import CaptureAborted, PacketPipeline
from dofus_prices.capture_errors import CaptureFunction, fail, run_guarded_capture
from dofus_prices.framing import Envelope
from dofus_prices.hdv import decode_lot_prices
from dofus_prices.market_stats import decode_market_stats
from dofus_prices.storage import StoreWriter
from dofus_prices.tcp import FlowKey
from dofus_prices.timeutil import format_utc

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


class EnvelopeHandler:
    """Decodes each envelope and submits its records to the writer."""

    def __init__(self, writer: StoreWriter, server: str, now: Clock) -> None:
        self._writer = writer
        self._server = server
        self._now = now
        self.submitted_count = 0

    def __call__(self, envelope: Envelope, key: FlowKey) -> None:
        captured_at = format_utc(self._now())
        lots = decode_lot_prices(envelope, self._server, captured_at)
        stats = decode_market_stats(envelope, self._server, captured_at)
        if lots:
            logger.info("item %d: %d lot prices", lots[0].item_id, len(lots))
        if stats:
            periods = ", ".join(row.period for row in stats)
            logger.info("item %d: %d market periods (%s)", stats[0].item_id, len(stats), periods)
        for record in [*lots, *stats]:
            self._writer.submit(record)
            self.submitted_count += 1


def make_envelope_handler(writer: StoreWriter, server: str, now: Clock) -> EnvelopeHandler:
    """Build the envelope callback storing lot prices and market stats via the writer."""
    return EnvelopeHandler(writer, server, now)


def _capture_and_drain(
    writer: StoreWriter, handler: EnvelopeHandler, interface: str | None, capture: CaptureFunction
) -> int:
    pipeline = PacketPipeline(handler)

    def stop_message() -> str:
        return f"Arrêt. {handler.submitted_count} messages décodés."

    def abort_message(error: CaptureAborted) -> str:
        return f"Capture interrompue ({error}) après {handler.submitted_count} messages décodés."

    try:
        return run_guarded_capture(capture, pipeline, interface, stop_message, abort_message)
    finally:
        writer.stop()


def run_command(arguments: argparse.Namespace, capture: CaptureFunction, now: Clock) -> int:
    """Capture HDV traffic into the database until Ctrl+C."""
    try:
        writer = StoreWriter(arguments.db)
    except (sqlite3.Error, OSError) as error:
        return fail(f"Impossible d'ouvrir la base de données {arguments.db} : {error}")
    print(f"Base de données : {arguments.db}. Serveur enregistré : {arguments.server}. "
          "Ctrl+C pour arrêter.")
    handler = make_envelope_handler(writer, arguments.server, now)
    return _capture_and_drain(writer, handler, arguments.interface, capture)
