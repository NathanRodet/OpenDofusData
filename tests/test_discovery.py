"""Tests for the discovery log: envelope description, logger and CLI."""

import json
from pathlib import Path

from dofus_prices import cli
from dofus_prices.discovery import (
    MAX_HEX_BYTES,
    MAX_TEXT_CHARS,
    DiscoveryLogger,
    describe_envelope,
)
from dofus_prices.framing import Envelope

VARINT_TAG = 0x08
LENGTH_TAG = 0x12
FIXED32_TAG = 0x1D
SERVER_PORT_KEY = ("1.2.3.4", 5555, "5.6.7.8", 40000)


def test_describe_envelope_lists_top_level_fields() -> None:
    payload = bytes([VARINT_TAG, 150 & 0x7F | 0x80, 1, LENGTH_TAG, 5]) + b"hello"
    payload += bytes([FIXED32_TAG]) + (7).to_bytes(4, "little")
    description = describe_envelope(Envelope("Demo", payload))
    assert description["type"] == "Demo"
    assert description["size"] == len(payload)
    assert description["fields"] == [
        {"number": 1, "wire_type": 0, "value": 150},
        {"number": 2, "wire_type": 2, "length": 5, "text": "hello"},
        {"number": 3, "wire_type": 5, "value": 7},
    ]


def test_describe_envelope_decodes_nested_message() -> None:
    inner = bytes([VARINT_TAG, 5])
    payload = bytes([LENGTH_TAG, len(inner)]) + inner
    field = describe_envelope(Envelope("Demo", payload))["fields"][0]
    assert field["length"] == 2
    assert field["fields"] == [{"number": 1, "wire_type": 0, "value": 5}]


def test_describe_envelope_survives_undecodable_payload() -> None:
    payload = bytes([0xFF]) * (MAX_HEX_BYTES + 10)
    description = describe_envelope(Envelope("Demo", payload))
    assert description["size"] == len(payload)
    assert description["fields"] == []
    assert description["hex"] == "ff" * MAX_HEX_BYTES


def test_describe_envelope_truncates_text_and_hex() -> None:
    long_text = b"a" * (MAX_TEXT_CHARS + 20)
    binary = bytes([0x80]) * (MAX_HEX_BYTES + 5)
    payload = bytes([LENGTH_TAG, len(long_text)]) + long_text
    payload += bytes([0x1A, len(binary)]) + binary
    fields = describe_envelope(Envelope("Demo", payload))["fields"]
    assert fields[0]["text"] == "a" * MAX_TEXT_CHARS
    assert fields[1]["hex"] == "80" * MAX_HEX_BYTES
    assert fields[1]["length"] == len(binary)


def test_discovery_logger_appends_one_json_line_per_envelope(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "discovery.jsonl"
    logger = DiscoveryLogger(str(path))
    logger.log(Envelope("A", bytes([VARINT_TAG, 1])), "client_to_server")
    logger.log(Envelope("B", b""), "server_to_client")
    logger.close()
    lines = path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert [record["type"] for record in records] == ["A", "B"]
    assert [record["direction"] for record in records] == ["client_to_server", "server_to_client"]
    assert records[0]["time"].endswith("+00:00")
    assert logger.logged_count == 2


def test_cli_discover_parses_arguments(tmp_path: Path, capsys) -> None:
    calls: list[tuple[str | None, int]] = []

    def fake_capture(pipeline, interface) -> None:
        calls.append((interface, 0))
        pipeline.on_envelope(Envelope("A", b""), SERVER_PORT_KEY)
        raise KeyboardInterrupt

    output = tmp_path / "log.jsonl"
    argv = ["discover", "--interface", "Ethernet", "--output", str(output)]
    assert cli.run(argv, capture=fake_capture) == 0
    assert calls == [("Ethernet", 0)]
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["direction"] == "server_to_client"
    assert "1" in capsys.readouterr().out


def test_cli_without_command_prints_help_and_fails(capsys) -> None:
    assert cli.main([]) != 0
    assert "discover" in capsys.readouterr().out


def test_cli_reports_capture_failure(tmp_path: Path, capsys) -> None:
    def failing_capture(pipeline, interface) -> None:
        raise PermissionError("denied")

    argv = ["discover", "--output", str(tmp_path / "log.jsonl")]
    assert cli.run(argv, capture=failing_capture) != 0
    assert "Npcap" in capsys.readouterr().err
