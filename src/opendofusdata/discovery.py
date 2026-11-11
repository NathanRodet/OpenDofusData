"""Discovery log: structure of each message (no raw packets, no text by default)."""

import argparse
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opendofusdata.framing import Envelope
from opendofusdata.protobuf import (
    WIRE_TYPE_LENGTH_DELIMITED,
    DecodeError,
    Field,
    read_varint,
    try_decode_fields,
)

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 4
MAX_TEXT_CHARS = 48
MAX_HEX_BYTES = 32
MAX_TYPED_HEX_BYTES = 64
MAX_PACKED_VALUES = 32
MAX_FIELDS_PER_MESSAGE = 64
MAX_LOG_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class _Preview:
    """Which opaque-byte previews to write: text/hex everywhere, or typed hex/packed."""

    include_text: bool
    typed_bytes: bool


def _packed_varints(content: bytes) -> list[int] | None:
    """Return all values if content is exactly a sequence of varints, else None."""
    values: list[int] = []
    offset = 0
    try:
        while offset < len(content):
            value, offset = read_varint(content, offset)
            values.append(value)
    except DecodeError:
        return None
    return values or None


def _typed_preview(content: bytes) -> dict[str, Any]:
    """Return the hex (up to MAX_TYPED_HEX_BYTES bytes) and, when the bytes are
    exactly varints, the packed values (up to MAX_PACKED_VALUES)."""
    preview: dict[str, Any] = {"hex": content[:MAX_TYPED_HEX_BYTES].hex()}
    packed = _packed_varints(content)
    if packed is not None:
        preview["packed"] = packed[:MAX_PACKED_VALUES]
    return preview


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
    fields: list[Field], depth: int, preview: _Preview
) -> dict[str, Any]:
    """Describe at most MAX_FIELDS_PER_MESSAGE fields, counting the dropped ones."""
    kept = fields[:MAX_FIELDS_PER_MESSAGE]
    description: dict[str, Any] = {
        "fields": [_describe_field(item, depth, preview) for item in kept]
    }
    if len(fields) > len(kept):
        description["fields_truncated"] = len(fields) - len(kept)
    return description


def _describe_bytes(content: bytes, depth: int, preview: _Preview) -> dict[str, Any]:
    """Describe a length-delimited value: its length and nested fields; when it is
    not a nested message, a text/hex preview (include_text) and/or the typed
    hex/packed preview (typed_bytes)."""
    description: dict[str, Any] = {"length": len(content)}
    nested = try_decode_fields(content) if depth < MAX_NESTING_DEPTH else None
    if nested:
        description.update(_describe_fields(nested, depth + 1, preview))
        return description
    if preview.include_text:
        description.update(_preview(content))
    if preview.typed_bytes:
        description.update(_typed_preview(content))
    return description


def _describe_field(item: Field, depth: int, preview: _Preview) -> dict[str, Any]:
    number, wire_type, value = item
    description: dict[str, Any] = {"number": number, "wire_type": wire_type}
    if wire_type == WIRE_TYPE_LENGTH_DELIMITED and isinstance(value, bytes):
        description.update(_describe_bytes(value, depth, preview))
    else:
        description["value"] = value
    return description


def describe_envelope(
    envelope: Envelope,
    include_text: bool = False,
    hex_types: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Describe type, size and field structure (numbers, wire types, integer values,
    lengths); text/hex previews of bytes are included only when include_text is set.
    For envelope types in hex_types, every opaque length-delimited field also gets
    "hex" (up to MAX_TYPED_HEX_BYTES bytes) and, if the bytes are exactly varints,
    "packed" (up to MAX_PACKED_VALUES integers)."""
    preview = _Preview(include_text, envelope.type_name in hex_types)
    description: dict[str, Any] = {"type": envelope.type_name, "size": len(envelope.payload)}
    fields = try_decode_fields(envelope.payload)
    description.update(_describe_fields(fields or [], 0, preview))
    if fields is None and include_text:
        description["hex"] = envelope.payload[:MAX_HEX_BYTES].hex()
    return description


class DiscoveryLogger:
    """Appends one JSON line per envelope to a file within a total size budget."""

    def __init__(
        self,
        path: str,
        include_text: bool = False,
        hex_types: frozenset[str] = frozenset(),
        max_bytes: int = MAX_LOG_BYTES,
    ) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._include_text = include_text
        self._hex_types = hex_types
        self._max_bytes = max_bytes
        self._written_bytes = os.path.getsize(path) if os.path.exists(path) else 0
        self._file = open(path, "a", encoding="utf-8")
        self.logged_count = 0

    def log(self, envelope: Envelope, direction: str) -> None:
        """Write the description of one envelope with its time and direction."""
        record = {"time": datetime.now(timezone.utc).isoformat(), "direction": direction}
        record.update(describe_envelope(envelope, self._include_text, self._hex_types))
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


def parse_hex_types(raw: str) -> frozenset[str]:
    """Parse comma-separated message type names (letters and digits only)."""
    names = raw.split(",")
    if not all(name.isascii() and name.isalnum() for name in names):
        raise argparse.ArgumentTypeError(
            "noms de types invalides (lettres et chiffres, séparés par des virgules)"
        )
    return frozenset(names)
