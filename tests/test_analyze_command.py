"""Tests of the analyze command (reads discovery logs, prints candidate messages)."""

import json
from pathlib import Path

from opendofusdata import cli
from opendofusdata.analyze_commands import parse_values
from opendofusdata.capture_errors import EXIT_FAILED, EXIT_OK
from opendofusdata.discovery import DiscoveryLogger
from tests.envelopes import lot_envelope, stats_envelope


def make_log(path: Path, *envelopes, hex_types=frozenset()) -> str:
    logger = DiscoveryLogger(str(path), hex_types=hex_types)
    for envelope in envelopes:
        logger.log(envelope, "server->client")
    logger.close()
    return str(path)


def run(*arguments: str) -> int:
    return cli.run(["analyze", *arguments], lambda pipeline, interface: None)


def test_parse_values_accepts_spaces_and_rejects_text() -> None:
    assert parse_values("307, 750,4") == frozenset({307, 750, 4})
    for bad in ("a,b", "1;2", ""):
        try:
            parse_values(bad)
        except Exception as error:
            assert "entiers" in str(error)
        else:
            raise AssertionError(f"{bad!r} must be refused")


def test_the_message_holding_the_values_is_printed_with_its_paths(tmp_path, capsys) -> None:
    action = make_log(tmp_path / "action.jsonl", lot_envelope(), stats_envelope(), hex_types=frozenset({"jzs"}))
    assert run(action, "--values", "307,750") == EXIT_OK
    output = capsys.readouterr().out
    assert "jzs" in output
    assert "307" in output and "1.1" in output
    assert "750" in output and "1.2#0" in output


def test_a_baseline_marks_types_already_present_without_the_action(tmp_path, capsys) -> None:
    baseline = make_log(tmp_path / "baseline.jsonl", stats_envelope())
    action = make_log(tmp_path / "action.jsonl", lot_envelope(), stats_envelope())
    assert run(action, "--baseline", baseline) == EXIT_OK
    lines = capsys.readouterr().out.splitlines()
    first_data_line = next(line for line in lines if line.startswith(("jzs", "ire")))
    assert first_data_line.startswith("jzs")


def test_values_missing_from_every_message_are_reported(tmp_path, capsys) -> None:
    action = make_log(tmp_path / "action.jsonl", stats_envelope())
    assert run(action, "--values", "424242") == EXIT_OK
    assert "424242" in capsys.readouterr().out


def test_top_limits_the_number_of_candidates(tmp_path, capsys) -> None:
    action = make_log(tmp_path / "action.jsonl", lot_envelope(), stats_envelope())
    run(action, "--top", "1")
    output = capsys.readouterr().out
    assert ("jzs" in output) != ("ire" in output)


def test_a_missing_log_is_a_clear_failure(tmp_path, capsys) -> None:
    assert run(str(tmp_path / "absent.jsonl")) == EXIT_FAILED
    assert "absent.jsonl" in capsys.readouterr().err


def test_an_empty_log_says_so(tmp_path, capsys) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert run(str(empty)) == EXIT_OK
    assert "Aucun message" in capsys.readouterr().out


def test_the_skeleton_flag_prints_constants_for_messages_ready_to_paste(tmp_path, capsys) -> None:
    action = make_log(tmp_path / "action.jsonl", lot_envelope(), hex_types=frozenset({"jzs"}))
    run(action, "--values", "307,750", "--skeleton")
    assert '"jzs"' in capsys.readouterr().out
