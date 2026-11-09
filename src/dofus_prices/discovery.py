"""Discovery log: describes the structure of each message, never raw packets."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dofus_prices.framing import Envelope
from dofus_prices.protobuf import WIRE_TYPE_LENGTH_DELIMITED, Field, try_decode_fields

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 4
MAX_TEXT_CHARS = 48
MAX_HEX_BYTES = 32


def _describe_bytes(content: bytes, depth: int) -> dict[str, Any]:
    """Describe a length-delimited value as nested fields, text or hex."""
    description: dict[str, Any] = {"length": len(content)}
    nested = try_decode_fields(content) if depth < MAX_NESTING_DEPTH else None
    if nested:
        description["fields"] = [_describe_field(item, depth + 1) for item in nested]
        return description
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    if text and text.isprintable():
        description["text"] = text[:MAX_TEXT_CHARS]
    else:
        description["hex"] = content[:MAX_HEX_BYTES].hex()
    return description


def _describe_field(item: Field, depth: int) -> dict[str, Any]:
    number, wire_type, value = item
    description: dict[str, Any] = {"number": number, "wire_type": wire_type}
    if wire_type == WIRE_TYPE_LENGTH_DELIMITED and isinstance(value, bytes):
        description.update(_describe_bytes(value, depth))
    else:
        description["value"] = value
    return description


def describe_envelope(envelope: Envelope) -> dict[str, Any]:
    """Describe an envelope's type, size and field structure (JSON-serialisable)."""
    description: dict[str, Any] = {"type": envelope.type_name, "size": len(envelope.payload)}
    fields = try_decode_fields(envelope.payload)
    description["fields"] = [_describe_field(item, 0) for item in fields or []]
    if fields is None:
        description["hex"] = envelope.payload[:MAX_HEX_BYTES].hex()
    return description


class DiscoveryLogger:
    """Appends one JSON line per envelope to a file, flushing after each line."""

    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._file = open(path, "a", encoding="utf-8")
        self.logged_count = 0

    def log(self, envelope: Envelope, direction: str) -> None:
        """Write the description of one envelope with its time and direction."""
        record = {"time": datetime.now(timezone.utc).isoformat(), "direction": direction}
        record.update(describe_envelope(envelope))
        self._file.write(json.dumps(record) + "\n")
        self._file.flush()
        self.logged_count += 1

    def close(self) -> None:
        """Close the log file."""
        self._file.close()
