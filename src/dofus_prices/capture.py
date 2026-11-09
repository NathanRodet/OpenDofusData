"""Passive packet capture: turns TCP segments into message envelopes."""

import logging
import time
from collections.abc import Callable
from typing import Any

from dofus_prices.framing import Envelope, EnvelopeExtractor
from dofus_prices.tcp import FlowKey, FlowTable, payload_length

logger = logging.getLogger(__name__)

DOFUS_PORT = 5555
BPF_FILTER = f"tcp port {DOFUS_PORT}"
PURGE_INTERVAL_SECONDS = 60.0
IP_HEADER_WORD_BYTES = 4
TCP_HEADER_WORD_BYTES = 4
DIRECTION_TO_SERVER = "client_to_server"
DIRECTION_TO_CLIENT = "server_to_client"


def direction_of(key: FlowKey) -> str:
    """Return the direction of a flow: the side using the Dofus port is the server."""
    return DIRECTION_TO_CLIENT if key[1] == DOFUS_PORT else DIRECTION_TO_SERVER


class PacketPipeline:
    """Feeds captured packets through TCP reassembly and envelope extraction."""

    def __init__(
        self,
        on_envelope: Callable[[Envelope, FlowKey], None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.on_envelope = on_envelope
        self._clock = clock
        self._flows = FlowTable()
        self._extractors: dict[FlowKey, EnvelopeExtractor] = {}
        self._last_purge = clock()

    def handle_packet(self, packet: Any) -> None:
        """Process one captured packet; never raises."""
        try:
            self._process(packet)
        except Exception:
            logger.exception("error while processing a packet")

    def _process(self, packet: Any) -> None:
        if not (packet.haslayer("IP") and packet.haslayer("TCP")):
            logger.debug("ignoring a non IPv4/TCP packet")
            return
        ip_layer, tcp_layer = packet["IP"], packet["TCP"]
        length = payload_length(
            ip_layer.len,
            ip_layer.ihl * IP_HEADER_WORD_BYTES,
            tcp_layer.dataofs * TCP_HEADER_WORD_BYTES,
        )
        now = self._clock()
        if length > 0:
            key = (ip_layer.src, tcp_layer.sport, ip_layer.dst, tcp_layer.dport)
            self._deliver(key, tcp_layer.seq, bytes(tcp_layer.payload)[:length], now)
        self._purge_if_due(now)

    def _deliver(self, key: FlowKey, seq: int, payload: bytes, now: float) -> None:
        reassembled = self._flows.feed(key, seq, payload, now)
        extractor = self._extractors.setdefault(key, EnvelopeExtractor())
        if reassembled.resynced:
            extractor.reset()
        for envelope in extractor.feed(reassembled.data):
            self.on_envelope(envelope, key)

    def _purge_if_due(self, now: float) -> None:
        if now - self._last_purge < PURGE_INTERVAL_SECONDS:
            return
        self._last_purge = now
        for key in self._flows.purge(now):
            self._extractors.pop(key, None)


def run_capture(pipeline: PacketPipeline, interface: str | None = None) -> None:
    """Sniff Dofus traffic and feed it to the pipeline until interrupted."""
    from scapy.all import sniff

    sniff(filter=BPF_FILTER, store=False, prn=pipeline.handle_packet, iface=interface)
