"""Discovery log: structure of each message (no raw packets, no text by default)."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dofus_prices.framing import Envelope
from dofus_prices.protobuf import WIRE_TYPE_LENGTH_DELIMITED, Field, try_decode_fields

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 4
MAX_TEXT_CHARS = 48
MAX_HEX_BYTES = 32
MAX_FIELDS_PER_MESSAGE = 64
MAX_LOG_BYTES = 100 * 1024 * 1024


class LogSizeLimitReached(Exception):
    """Raised when writing a line would exceed the log size budget."""


def _preview(content: bytes) -> dict[str, str]:
    """Return a truncated text preview if printable UTF-8, else a truncated hex preview."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    if text and text.isprintable():
        return {"text": text[:MAX_TEXT_CHARS]}
    return {"hex": content[:MAX_HEX_BYTES].hex()}


def _describe_fields(
    fields: list[Field], depth: int, include_text: bool
) -> dict[str, Any]:
    """Describe at most MAX_FIELDS_PER_MESSAGE fields, counting the dropped ones."""
    kept = fields[:MAX_FIELDS_PER_MESSAGE]
    description: dict[str, Any] = {
        "fields": [_describe_field(item, depth, include_text) for item in kept]
    }
    if len(fields) > len(kept):
        description["fields_truncated"] = len(fields) - len(kept)
    return description


def _describe_bytes(content: bytes, depth: int, include_text: bool) -> dict[str, Any]:
    """Describe a length-delimited value: its length and nested fields; with
    include_text, a truncated text or hex preview when it is not a nested message."""
    description: dict[str, Any] = {"length": len(content)}
    nested = try_decode_fields(content) if depth < MAX_NESTING_DEPTH else None
    if nested:
        description.update(_describe_fields(nested, depth + 1, include_text))
    elif include_text:
        description.update(_preview(content))
    return description


def _describe_field(item: Field, depth: int, include_text: bool) -> dict[str, Any]:
    number, wire_type, value = item
    description: dict[str, Any] = {"number": number, "wire_type": wire_type}
    if wire_type == WIRE_TYPE_LENGTH_DELIMITED and isinstance(value, bytes):
        description.update(_describe_bytes(value, depth, include_text))
    else:
        description["value"] = value
    return description


def describe_envelope(envelope: Envelope, include_text: bool = False) -> dict[str, Any]:
    """Describe type, size and field structure (numbers, wire types, integer values,
    lengths); text/hex previews of bytes are included only when include_text is set."""
    description: dict[str, Any] = {"type": envelope.type_name, "size": len(envelope.payload)}
    fields = try_decode_fields(envelope.payload)
    description.update(_describe_fields(fields or [], 0, include_text))
    if fields is None and include_text:
        description["hex"] = envelope.payload[:MAX_HEX_BYTES].hex()
    return description


class DiscoveryLogger:
    """Appends one JSON line per envelope to a file within a total size budget."""

    def __init__(
        self, path: str, include_text: bool = False, max_bytes: int = MAX_LOG_BYTES
    ) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._include_text = include_text
        self._max_bytes = max_bytes
        self._written_bytes = os.path.getsize(path) if os.path.exists(path) else 0
        self._file = open(path, "a", encoding="utf-8")
        self.logged_count = 0

    def log(self, envelope: Envelope, direction: str) -> None:
        """Write the description of one envelope with its time and direction."""
        record = {"time": datetime.now(timezone.utc).isoformat(), "direction": direction}
        record.update(describe_envelope(envelope, self._include_text))
        line = json.dumps(record) + "\n"
        size = len(line.encode("utf-8"))
        if self._written_bytes + size > self._max_bytes:
            raise LogSizeLimitReached(f"log size limit of {self._max_bytes} bytes reached")
        self._file.write(line)
        self._file.flush()
        self._written_bytes += size
        self.logged_count += 1

    def close(self) -> None:
        """Close the log file."""
        self._file.close()
