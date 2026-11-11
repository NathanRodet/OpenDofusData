"""Passive packet capture: turns TCP segments into message envelopes."""

import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

from opendofusdata.framing import Envelope, EnvelopeExtractor
from opendofusdata.tcp import DEFAULT_MAX_FLOWS, FlowKey, FlowTable, payload_length

logger = logging.getLogger(__name__)

DOFUS_PORT = 5555
BPF_FILTER = f"tcp port {DOFUS_PORT}"
PURGE_INTERVAL_SECONDS = 60.0
IP_HEADER_WORD_BYTES = 4
TCP_HEADER_WORD_BYTES = 4
DIRECTION_TO_SERVER = "client_to_server"
DIRECTION_TO_CLIENT = "server_to_client"


class CaptureAborted(Exception):
    """Raised by an envelope callback to stop the capture (for example, disk full)."""


def direction_of(key: FlowKey) -> str:
    """Return the direction of a flow: the side using the Dofus port is the server."""
    return DIRECTION_TO_CLIENT if key[1] == DOFUS_PORT else DIRECTION_TO_SERVER


class PacketPipeline:
    """Feeds captured packets through TCP reassembly and envelope extraction."""

    def __init__(
        self,
        on_envelope: Callable[[Envelope, FlowKey], None],
        clock: Callable[[], float] = time.monotonic,
        max_flows: int = DEFAULT_MAX_FLOWS,
    ) -> None:
        self.on_envelope = on_envelope
        self._clock = clock
        self._flows = FlowTable(max_flows=max_flows)
        self._extractors: dict[FlowKey, EnvelopeExtractor] = {}
        self._last_purge = clock()
        self._offload_warned = False
        self._first_message_seen = False
        self._ipv6_warned = False
        self.abort_error: CaptureAborted | None = None

    def handle_packet(self, packet: Any) -> None:
        """Process one captured packet; never raises."""
        try:
            self._process(packet)
        except CaptureAborted as error:
            self.abort_error = error
            raise
        except Exception:
            logger.exception("error while processing a packet")

    def _process(self, packet: Any) -> None:
        if not (packet.haslayer("IP") and packet.haslayer("TCP")):
            self._ignore_unsupported(packet)
            return
        ip_layer, tcp_layer = packet["IP"], packet["TCP"]
        data = bytes(tcp_layer.payload)[: self._tcp_data_length(ip_layer, tcp_layer)]
        now = self._clock()
        if data:
            key = (ip_layer.src, tcp_layer.sport, ip_layer.dst, tcp_layer.dport)
            self._deliver(key, tcp_layer.seq, data, now)
        else:
            logger.debug("skipping a segment without TCP data")
        self._purge_if_due(now)

    def _ignore_unsupported(self, packet: Any) -> None:
        if packet.haslayer("IPv6") and packet.haslayer("TCP"):
            self._warn_ipv6_once()
        logger.debug("ignoring a non IPv4/TCP packet")

    def _warn_ipv6_once(self) -> None:
        if not self._ipv6_warned:
            self._ipv6_warned = True
            logger.warning("IPv6 is not supported: dropping IPv6 traffic on the game port")

    def _tcp_data_length(self, ip_layer: Any, tcp_layer: Any) -> int:
        """Return the TCP data length; a zero IP length means segmentation offload."""
        if ip_layer.len == 0:
            self._warn_offload_once()
            return len(bytes(tcp_layer.payload))
        return payload_length(
            ip_layer.len,
            ip_layer.ihl * IP_HEADER_WORD_BYTES,
            tcp_layer.dataofs * TCP_HEADER_WORD_BYTES,
        )

    def _warn_offload_once(self) -> None:
        if not self._offload_warned:
            self._offload_warned = True
            logger.warning(
                "IP lengths are zero, which indicates segmentation offload; "
                "using captured lengths instead"
            )

    def _deliver(self, key: FlowKey, seq: int, payload: bytes, now: float) -> None:
        reassembled = self._flows.feed(key, seq, payload, now)
        for evicted_key in self._flows.take_evicted():
            self._extractors.pop(evicted_key, None)
        extractor = self._extractors.get(key)
        if extractor is None:
            extractor = self._extractors[key] = EnvelopeExtractor()
        if reassembled.resynced:
            extractor.reset()
        for envelope in extractor.feed(reassembled.data):
            self._notify(envelope, key)

    def _notify(self, envelope: Envelope, key: FlowKey) -> None:
        """Call the callback for one envelope, containing its failures."""
        self._log_first_message_once()
        try:
            self.on_envelope(envelope, key)
        except CaptureAborted:
            raise
        except Exception:
            logger.exception("error in the envelope callback")

    def _log_first_message_once(self) -> None:
        if not self._first_message_seen:
            self._first_message_seen = True
            logger.info("first Dofus message seen: capture is working")

    def _purge_if_due(self, now: float) -> None:
        if now - self._last_purge < PURGE_INTERVAL_SECONDS:
            return
        self._last_purge = now
        for key in self._flows.purge(now):
            self._extractors.pop(key, None)


class SniffFunction(Protocol):
    """The subset of scapy.sendrecv.sniff used by run_capture."""

    def __call__(self, **kwargs: Any) -> Any: ...


def _load_scapy_sniff() -> SniffFunction:
    from scapy.all import sniff

    return sniff


def sniff_arguments(pipeline: PacketPipeline, interface: str | None) -> dict[str, Any]:
    return {
        "filter": BPF_FILTER,
        "store": False,
        "prn": pipeline.handle_packet,
        "iface": interface,
        "chainCC": True,
        "stop_filter": lambda packet: pipeline.abort_error is not None,
    }


def run_capture(
    pipeline: PacketPipeline,
    interface: str | None = None,
    sniff_function: SniffFunction | None = None,
) -> None:
    """Sniff Dofus traffic and feed it to the pipeline until interrupted.

    Scapy's sniff swallows every exception raised by its callback and, unless
    chainCC is set, KeyboardInterrupt too. So chainCC=True lets Ctrl+C propagate,
    and a CaptureAborted recorded by the pipeline is re-raised here once sniff has
    returned. Scapy already ends the loop at once when the callback raises (it closes
    the failed socket); stop_filter is only a safeguard. Stale abort state is cleared first.
    """
    pipeline.abort_error = None
    sniff = sniff_function or _load_scapy_sniff()
    sniff(**sniff_arguments(pipeline, interface))
    if pipeline.abort_error is not None:
        raise pipeline.abort_error
