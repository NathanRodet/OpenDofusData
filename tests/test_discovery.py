"""Tests for the discovery log: envelope description, logger and CLI."""

import json
from pathlib import Path

import pytest

from dofus_prices import cli
from dofus_prices.discovery import (
    MAX_HEX_BYTES,
    MAX_PACKED_VALUES,
    MAX_TYPED_HEX_BYTES,
    MAX_TEXT_CHARS,
    MAX_FIELDS_PER_MESSAGE,
    DiscoveryLogger,
    LogSizeLimitReached,
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
    description = describe_envelope(Envelope("Demo", payload), include_text=True)
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
    description = describe_envelope(Envelope("Demo", payload), include_text=True)
    assert description["size"] == len(payload)
    assert description["fields"] == []
    assert description["hex"] == "ff" * MAX_HEX_BYTES


def test_describe_envelope_truncates_text_and_hex() -> None:
    long_text = b"a" * (MAX_TEXT_CHARS + 20)
    binary = bytes([0x80]) * (MAX_HEX_BYTES + 5)
    payload = bytes([LENGTH_TAG, len(long_text)]) + long_text
    payload += bytes([0x1A, len(binary)]) + binary
    fields = describe_envelope(Envelope("Demo", payload), include_text=True)["fields"]
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


def test_cli_capture_failures_print_one_message_without_traceback(
    tmp_path: Path, capsys
) -> None:
    for error in (RuntimeError("winpcap is not installed"), ValueError("bad interface")):
        def failing_capture(pipeline, interface, error=error) -> None:
            raise error

        argv = ["discover", "--output", str(tmp_path / "log.jsonl")]
        assert cli.run(argv, capture=failing_capture) != 0
        captured = capsys.readouterr()
        assert str(error) in captured.err
        assert "Npcap" in captured.err
        assert "Traceback" not in captured.err + captured.out


def test_cli_unwritable_output_path_fails_with_message(tmp_path: Path, capsys) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    argv = ["discover", "--output", str(blocker / "log.jsonl")]
    assert cli.run(argv, capture=lambda pipeline, interface: None) != 0
    assert str(blocker) in capsys.readouterr().err


def test_cli_log_write_failure_aborts_capture(tmp_path: Path, monkeypatch, capsys) -> None:
    def failing_log(self, envelope, direction) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(DiscoveryLogger, "log", failing_log)

    def fake_capture(pipeline, interface) -> None:
        pipeline.on_envelope(Envelope("A", b""), SERVER_PORT_KEY)

    argv = ["discover", "--output", str(tmp_path / "log.jsonl")]
    assert cli.run(argv, capture=fake_capture) != 0
    assert "disk full" in capsys.readouterr().err


def _keys_anywhere(value) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys |= {key} | _keys_anywhere(item)
    elif isinstance(value, list):
        for item in value:
            keys |= _keys_anywhere(item)
    return keys


def _text_and_nested_payload() -> bytes:
    inner = bytes([LENGTH_TAG, 5]) + b"hello"
    return bytes([LENGTH_TAG, len(inner)]) + inner + bytes([0x1A, 2, 0xFF, 0xFF])


def test_default_description_has_no_text_or_hex_anywhere() -> None:
    for payload in (_text_and_nested_payload(), bytes([0xFF]) * 5):
        description = describe_envelope(Envelope("Demo", payload))
        assert not {"text", "hex"} & _keys_anywhere(description)
    assert description["fields"] == []


def test_opt_in_description_has_text_and_hex() -> None:
    description = describe_envelope(Envelope("Demo", _text_and_nested_payload()), include_text=True)
    assert {"text", "hex"} <= _keys_anywhere(description)


def test_field_count_is_capped_with_truncation_count() -> None:
    payload = bytes([VARINT_TAG, 1]) * (MAX_FIELDS_PER_MESSAGE + 6)
    description = describe_envelope(Envelope("Demo", payload))
    assert len(description["fields"]) == MAX_FIELDS_PER_MESSAGE
    assert description["fields_truncated"] == 6
    size = len(payload)
    nested = bytes([LENGTH_TAG, size & 0x7F | 0x80, size >> 7]) + payload
    field = describe_envelope(Envelope("Demo", nested))["fields"][0]
    assert field["fields_truncated"] == 6


def test_logger_refuses_lines_beyond_the_size_budget(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    logger = DiscoveryLogger(str(path), max_bytes=300)
    logger.log(Envelope("A", b""), "client_to_server")
    with pytest.raises(LogSizeLimitReached):
        for _ in range(10):
            logger.log(Envelope("A", b""), "client_to_server")
    logger.close()
    assert path.stat().st_size <= 300
    reopened = DiscoveryLogger(str(path), max_bytes=path.stat().st_size + 1)
    with pytest.raises(LogSizeLimitReached):
        reopened.log(Envelope("A", b""), "client_to_server")
    reopened.close()


def test_cli_include_text_flag_is_passed_through(tmp_path: Path, capsys) -> None:
    output = tmp_path / "log.jsonl"
    payload = bytes([LENGTH_TAG, 5]) + b"hello"

    def fake_capture(pipeline, interface) -> None:
        pipeline.on_envelope(Envelope("A", payload), SERVER_PORT_KEY)
        raise KeyboardInterrupt

    assert cli.run(["discover", "--output", str(output), "--include-text"], fake_capture) == 0
    assert '"text": "hello"' in output.read_text(encoding="utf-8")
    assert "personnelles" in capsys.readouterr().out
    other = tmp_path / "default.jsonl"
    cli.run(["discover", "--output", str(other)], fake_capture)
    assert "hello" not in other.read_text(encoding="utf-8")


def test_cli_size_limit_aborts_with_message(tmp_path: Path, monkeypatch, capsys) -> None:
    def refusing_log(self, envelope, direction) -> None:
        raise LogSizeLimitReached("limit")

    monkeypatch.setattr(DiscoveryLogger, "log", refusing_log)

    def fake_capture(pipeline, interface) -> None:
        pipeline.on_envelope(Envelope("A", b""), SERVER_PORT_KEY)

    assert cli.run(["discover", "--output", str(tmp_path / "l.jsonl")], fake_capture) != 0
    assert "limite de taille" in capsys.readouterr().err


PACKED_VALUES = [750, 5868, 49993, 499999]
PACKED_BYTES = bytes([0xEE, 0x05, 0xEC, 0x2D, 0xC9, 0x86, 0x03, 0x9F, 0xC2, 0x1E])


def _length_field(content: bytes, tag: int = LENGTH_TAG) -> bytes:
    return bytes([tag, len(content)]) + content


def test_hex_types_adds_hex_and_packed_for_named_type_only() -> None:
    payload = _length_field(PACKED_BYTES)
    named = describe_envelope(Envelope("jzs", payload), hex_types=frozenset({"jzs"}))
    field = named["fields"][0]
    assert field["packed"] == PACKED_VALUES
    assert field["hex"] == PACKED_BYTES.hex()
    for description in (
        describe_envelope(Envelope("other", payload), hex_types=frozenset({"jzs"})),
        describe_envelope(Envelope("jzs", payload)),
    ):
        assert not {"hex", "packed"} & _keys_anywhere(description)


def test_hex_types_text_field_gets_hex_and_nested_message_does_not() -> None:
    nested = _length_field(PACKED_BYTES)
    payload = _length_field(b"Hi!") + _length_field(nested, 0x1A)
    fields = describe_envelope(Envelope("jzs", payload), hex_types=frozenset({"jzs"}))["fields"]
    assert fields[0]["hex"] == b"Hi!".hex()
    assert "text" not in fields[0]
    assert "hex" not in fields[1]
    assert fields[1]["fields"][0]["packed"] == PACKED_VALUES


def test_hex_types_previews_are_capped() -> None:
    many = bytes([1]) * (MAX_PACKED_VALUES + 8)
    long_binary = bytes([0xFF]) * (MAX_TYPED_HEX_BYTES + 8)
    payload = _length_field(many) + _length_field(long_binary, 0x1A)
    fields = describe_envelope(Envelope("jzs", payload), hex_types=frozenset({"jzs"}))["fields"]
    assert len(fields[0]["packed"]) == MAX_PACKED_VALUES
    assert fields[1]["hex"] == "ff" * MAX_TYPED_HEX_BYTES
    assert "packed" not in fields[1]


def test_logger_passes_hex_types(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    logger = DiscoveryLogger(str(path), hex_types=frozenset({"jzs"}))
    logger.log(Envelope("jzs", _length_field(PACKED_BYTES)), "server_to_client")
    logger.close()
    assert json.loads(path.read_text(encoding="utf-8"))["fields"][0]["packed"] == PACKED_VALUES


def test_cli_hex_types_is_passed_through_with_one_notice(tmp_path: Path, capsys) -> None:
    output = tmp_path / "log.jsonl"

    def fake_capture(pipeline, interface) -> None:
        pipeline.on_envelope(Envelope("ire", _length_field(PACKED_BYTES)), SERVER_PORT_KEY)
        raise KeyboardInterrupt

    argv = ["discover", "--output", str(output), "--hex-types", "jzs,ire"]
    assert cli.run(argv, fake_capture) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["fields"][0]["packed"] == PACKED_VALUES
    out = capsys.readouterr().out
    assert out.count("ire, jzs") == 1
    assert out.count("données personnelles si ces types transportent du chat") == 1
    assert "Attention : le journal" not in out
    cli.run(["discover", "--output", str(tmp_path / "d.jsonl")], fake_capture)
    assert "Aperçus d'octets" not in capsys.readouterr().out


@pytest.mark.parametrize("value", ["jzs;ire", "jzs,,ire", "", "jz s"])
def test_cli_rejects_invalid_hex_types(value: str) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["discover", "--hex-types", value])


def test_hex_types_with_include_text_gives_both_and_typed_hex_wins() -> None:
    long_text = b"a" * (MAX_TYPED_HEX_BYTES - 4)
    payload = _length_field(long_text)
    field = describe_envelope(
        Envelope("jzs", payload), include_text=True, hex_types=frozenset({"jzs"})
    )["fields"][0]
    assert field["text"] == "a" * MAX_TEXT_CHARS
    assert field["hex"] == long_text.hex()
    assert "packed" in field


def test_hex_types_match_is_case_sensitive() -> None:
    description = describe_envelope(
        Envelope("JZS", _length_field(PACKED_BYTES)), hex_types=frozenset({"jzs"})
    )
    assert not {"hex", "packed"} & _keys_anywhere(description)
