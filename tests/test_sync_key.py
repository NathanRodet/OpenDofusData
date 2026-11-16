"""The key of the player: format check, cleaning and local storage in config.json."""

import json
import logging
from pathlib import Path

import pytest

from opendofusdata.sync_key import KEY_PATTERN, SYNC_KEY_CONFIG, clean_key, key_format_ok, load_sync_key, save_sync_key

# The same key as the server suite (src/server/tests/test_signed_keys.py).
VECTOR_KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"


def test_the_vector_key_matches_the_pattern() -> None:
    assert KEY_PATTERN.fullmatch(VECTOR_KEY)
    assert key_format_ok(VECTOR_KEY)


@pytest.mark.parametrize("text", [
    "", "odk1", VECTOR_KEY + "A", VECTOR_KEY[:-1], VECTOR_KEY.replace("odk1", "odk2"), "Bearer " + VECTOR_KEY,
    VECTOR_KEY + "\n", VECTOR_KEY.replace(".", "-"), "odk1.AAAAAAAAAAA", VECTOR_KEY.replace("A", "é", 1),
])
def test_format_is_strict(text: str) -> None:
    assert not key_format_ok(text)


@pytest.mark.parametrize("pasted", [f"  {VECTOR_KEY}\n", f"\t{VECTOR_KEY}\r\n", f"odk1.AAAAAAAAAAA.\n{VECTOR_KEY[17:]}"])
def test_clean_key_removes_spaces_tabs_and_line_breaks(pasted: str) -> None:
    assert clean_key(pasted) == VECTOR_KEY


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    assert save_sync_key(path, VECTOR_KEY)
    assert load_sync_key(path) == VECTOR_KEY
    assert json.loads(path.read_text(encoding="utf-8"))[SYNC_KEY_CONFIG] == VECTOR_KEY


def test_saving_keeps_the_other_settings(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"server": "Brial"}), encoding="utf-8")
    save_sync_key(path, VECTOR_KEY)
    assert json.loads(path.read_text(encoding="utf-8"))["server"] == "Brial"


def test_an_invalid_key_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    assert not save_sync_key(path, "pas une clé")
    assert not path.exists()


def test_none_removes_the_key_and_keeps_the_rest(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"server": "Brial", SYNC_KEY_CONFIG: VECTOR_KEY}), encoding="utf-8")
    assert save_sync_key(path, None)
    assert load_sync_key(path) is None
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["server"] == "Brial" and SYNC_KEY_CONFIG not in document


@pytest.mark.parametrize("stored", [None, 12, "", "pas une clé", ["x"], {"a": 1}, VECTOR_KEY + "x"])
def test_load_ignores_anything_that_is_not_a_well_formed_key(tmp_path: Path, stored: object) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({SYNC_KEY_CONFIG: stored}), encoding="utf-8")
    assert load_sync_key(path) is None


def test_missing_or_corrupt_config_does_not_crash(tmp_path: Path) -> None:
    assert load_sync_key(tmp_path / "absent.json") is None
    corrupt = tmp_path / "config.json"
    corrupt.write_text("{pas du json", encoding="utf-8")
    assert load_sync_key(corrupt) is None


def test_a_write_failure_returns_false_without_logging_the_key(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a folder", encoding="utf-8")
    with caplog.at_level(logging.DEBUG):
        assert not save_sync_key(blocker / "config.json", VECTOR_KEY)
    assert VECTOR_KEY not in caplog.text
