"""The run command: decodes captured envelopes and hands records to the store writer."""

import argparse
import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

from opendofusdata.capture import DIRECTION_TO_CLIENT, CaptureAborted, PacketPipeline, direction_of
from opendofusdata.capture_errors import CaptureFunction, fail, run_guarded_capture
from opendofusdata.framing import Envelope
from opendofusdata.hdv import decode_lot_prices
from opendofusdata.market_stats import decode_market_stats
from opendofusdata.breaking import BreakingTracker
from opendofusdata.categories import DEFAULT_ENABLED, CategorySettings, FilteringWriter
from opendofusdata.pets import PetTracker
from opendofusdata.recycling import RecyclingTracker
from opendofusdata.records import LotPrice, MarketStats
from opendofusdata.storage import StoreWriter
from opendofusdata.tcp import FlowKey
from opendofusdata.timeutil import format_utc
from opendofusdata.verbose_table import format_lot_prices, format_market_stats

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]
Echo = Callable[[str], None]


def utc_now() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


class EnvelopeHandler:
    """Decodes each envelope and submits its records to the writer.

    When `echo` is given, the decoded values are also passed to it as text tables. The
    echo runs on the capture thread, which is acceptable for this debug option. If it
    raises OSError (for example a closed console) or UnicodeError (a console that cannot
    encode accents), one warning is logged and echoing stops.
    """

    def __init__(self, writer: StoreWriter, server: str, now: Clock, echo: Echo | None = None) -> None:
        self._writer = writer
        self._server = server
        self._now = now
        self._echo = echo
        self._recycling = RecyclingTracker(server)
        self._pets = PetTracker(server)
        self._breaking = BreakingTracker(server)
        self.submitted_count = 0

    def __call__(self, envelope: Envelope, key: FlowKey) -> None:
        captured_at = format_utc(self._now())
        lots = decode_lot_prices(envelope, self._server, captured_at)
        stats = decode_market_stats(envelope, self._server, captured_at)
        self._log(lots, stats)
        from_server = direction_of(key) == DIRECTION_TO_CLIENT
        others = [self._recycling.feed(envelope, from_server, captured_at),
                  self._pets.feed(envelope, from_server, captured_at),
                  self._breaking.feed(envelope, from_server, captured_at)]
        for record in [*lots, *stats, *(record for record in others if record)]:
            self._writer.submit(record)
            self.submitted_count += 1
        self._show(lots, stats)

    def _log(self, lots: list[LotPrice], stats: list[MarketStats]) -> None:
        if lots:
            logger.info("item %d: %d lot prices", lots[0].item_id, len(lots))
        if stats:
            periods = ", ".join(row.period for row in stats)
            logger.info("item %d: %d market periods (%s)", stats[0].item_id, len(stats), periods)

    def _show(self, lots: list[LotPrice], stats: list[MarketStats]) -> None:
        for block in (format_lot_prices(lots), format_market_stats(stats)):
            if block and self._echo is not None:
                self._echo_block(block)

    def _echo_block(self, block: str) -> None:
        try:
            self._echo(block + "\n")  # the extra newline leaves a blank line once printed
        except (OSError, UnicodeError) as error:
            logger.warning("affichage --verbose désactivé (%s); la capture continue", error)
            self._echo = None


def make_envelope_handler(
    writer: StoreWriter, server: str, now: Clock, echo: Echo | None = None
) -> EnvelopeHandler:
    """Build the envelope callback storing lot prices and market stats via the writer."""
    return EnvelopeHandler(writer, server, now, echo)


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


def run_command(
    arguments: argparse.Namespace, capture: CaptureFunction, now: Clock,
    categories: CategorySettings | None = None,
) -> int:
    """Capture into the database until Ctrl+C, recording only the enabled categories (HDV by default)."""
    try:
        writer = StoreWriter(arguments.db)
    except (sqlite3.Error, OSError) as error:
        return fail(f"Impossible d'ouvrir la base de données {arguments.db} : {error}")
    label = getattr(arguments, "server_label", "")
    print(f"Base de données : {arguments.db}. Serveur enregistré : {arguments.server}{label}. "
          "Ctrl+C pour arrêter.")
    echo = print if arguments.verbose else None
    consent = categories if categories is not None else CategorySettings(DEFAULT_ENABLED)
    handler = make_envelope_handler(FilteringWriter(writer, consent), arguments.server, now, echo)
    return _capture_and_drain(writer, handler, arguments.interface, capture)
