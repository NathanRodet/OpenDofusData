"""Tests of the discovery-log analysis that finds which message carries given on-screen values."""

import json
from pathlib import Path

from opendofusdata.capture_analysis import (
    find_candidates, integer_paths, load_records, skeleton,
)
from opendofusdata.discovery import DiscoveryLogger
from tests.envelopes import lot_envelope

TO_CLIENT = "server->client"


def message(type_name: str, fields: list[dict], direction: str = TO_CLIENT, size: int = 10) -> dict:
    return {"time": "2026-11-11T10:00:00+00:00", "direction": direction, "type": type_name,
            "size": size, "fields": fields}


def int_field(number: int, value: int) -> dict:
    return {"number": number, "wire_type": 0, "value": value}


def nested(number: int, fields: list[dict]) -> dict:
    return {"number": number, "wire_type": 2, "length": 5, "fields": fields}


def packed(number: int, values: list[int]) -> dict:
    return {"number": number, "wire_type": 2, "length": 5, "hex": "00", "packed": values}


def test_integer_paths_follow_nesting_and_packed_positions() -> None:
    record = message("abc", [int_field(2, 5), nested(1, [int_field(1, 33528), packed(2, [750, 5868])])])
    paths = integer_paths(record)
    assert paths[5] == {"2"}
    assert paths[33528] == {"1.1"}
    assert paths[750] == {"1.2#0"}
    assert paths[5868] == {"1.2#1"}


def test_repeated_fields_share_one_path() -> None:
    record = message("abc", [nested(1, [int_field(2, 7)]), nested(1, [int_field(2, 7)])])
    assert integer_paths(record)[7] == {"1.2"}


def test_the_message_holding_most_of_the_values_ranks_first() -> None:
    action = [message("few", [int_field(1, 33528)]),
              message("many", [int_field(1, 33528), nested(2, [int_field(1, 4), int_field(2, 120)])]),
              message("none", [int_field(1, 999)])]
    candidates = find_candidates(action, [], {33528, 4, 120})
    assert [candidate.type_name for candidate in candidates] == ["many", "few", "none"]
    assert [hit.value for hit in candidates[0].hits] == [4, 120, 33528]


def test_when_values_tie_a_type_absent_from_the_baseline_ranks_first() -> None:
    action = [message("common", [int_field(1, 7)]), message("new", [int_field(1, 7)])]
    baseline = [message("common", [int_field(1, 1)])]
    candidates = find_candidates(action, baseline, {7})
    assert [candidate.type_name for candidate in candidates] == ["new", "common"]
    assert candidates[1].baseline_count == 1


def test_without_values_new_types_come_first_then_the_most_frequent() -> None:
    action = [message("noise", [int_field(1, 1)])] * 5 + [message("rare", [int_field(1, 2)])]
    baseline = [message("noise", [int_field(1, 1)])] * 5
    assert [c.type_name for c in find_candidates(action, baseline, set())] == ["rare", "noise"]


def test_counts_sizes_and_directions_are_aggregated_per_type_and_direction() -> None:
    action = [message("abc", [], size=10), message("abc", [], size=30),
              message("abc", [], direction="client->server", size=4)]
    by_direction = {candidate.direction: candidate for candidate in find_candidates(action, [], set())}
    assert (by_direction[TO_CLIENT].count, by_direction[TO_CLIENT].min_size,
            by_direction[TO_CLIENT].max_size) == (2, 10, 30)
    assert by_direction["client->server"].count == 1


def test_load_records_skips_blank_and_invalid_lines(tmp_path, caplog) -> None:
    path = tmp_path / "log.jsonl"
    path.write_text(json.dumps(message("abc", [])) + "\n\nnot json\n[1, 2]\n" + json.dumps(message("def", [])) + "\n",
                    encoding="utf-8")
    assert [record["type"] for record in load_records(str(path))] == ["abc", "def"]
    assert "ligne 3" in caplog.text


def test_load_records_of_a_missing_file_is_an_error_the_caller_can_report(tmp_path) -> None:
    try:
        load_records(str(tmp_path / "absent.jsonl"))
    except OSError:
        return
    raise AssertionError("an absent log must raise OSError")


def test_skeleton_lists_the_type_and_where_each_value_sits() -> None:
    candidates = find_candidates([message("abc", [int_field(1, 33528), nested(2, [int_field(1, 4)])])], [],
                                 {33528, 4})
    text = skeleton(candidates[0])
    assert '"abc"' in text
    assert "33528" in text and "1" in text
    assert "2.1" in text


def test_the_known_hdv_message_is_found_from_the_item_and_a_price(tmp_path) -> None:
    path = tmp_path / "hdv.jsonl"
    logger = DiscoveryLogger(str(path), hex_types=frozenset({"jzs"}))
    logger.log(lot_envelope(), TO_CLIENT)
    logger.close()
    candidates = find_candidates(load_records(str(path)), [], {307, 750})
    assert candidates[0].type_name == "jzs"
    paths = {hit.value: hit.paths for hit in candidates[0].hits}
    assert paths[307] == ("1.1",)
    assert paths[750] == ("1.2#0",)


def test_a_value_that_appears_nowhere_is_reported_missing_not_invented() -> None:
    candidates = find_candidates([message("abc", [int_field(1, 1)])], [], {424242})
    assert candidates[0].hits == ()


HOSTILE_TYPE = 'abc"\n__import__("os").system("x")\x1b[31m'


def test_hostile_message_and_direction_names_are_made_safe() -> None:
    records = [message(HOSTILE_TYPE, [int_field(1, 5)], direction="to\nclient\x1b[0m")]
    candidate = find_candidates(records, [], {5})[0]
    for text in (candidate.type_name, candidate.direction):
        assert text.isprintable()
        assert '"' not in text
        assert "\n" not in text
    assert candidate.type_name.startswith("abc")


def test_a_hostile_name_cannot_break_out_of_the_skeleton() -> None:
    candidate = find_candidates([message(HOSTILE_TYPE, [int_field(1, 5)])], [], {5})[0]
    lines = skeleton(candidate).splitlines()
    assert len(lines) == 2
    assert lines[0].startswith('NEW_MESSAGE_TYPE = "')
    assert lines[0].count('"') == 2
    assert lines[1].startswith("# 5 ")


def test_very_long_names_are_cut() -> None:
    candidate = find_candidates([message("x" * 500, [])], [], set())[0]
    assert len(candidate.type_name) <= 80


def test_normal_names_are_unchanged() -> None:
    candidate = find_candidates([message("jzs", [])], [], set())[0]
    assert (candidate.type_name, candidate.direction) == ("jzs", TO_CLIENT)
