"""The administrator's local registry: who got which key, never the keys themselves."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from opendofusdata.admin_registry import MAX_LABEL_LENGTH, AdminRegistry, LabelExistsError, clean_label

MOMENT = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def registry(tmp_path: Path) -> AdminRegistry:
    return AdminRegistry(tmp_path / "admin_keys.json", lambda: MOMENT)


def test_add_then_read_back_across_instances(tmp_path: Path) -> None:
    entry = registry(tmp_path).add("Joueur Un", "AAAAAAAAAAA")
    assert (entry.label, entry.key_id, entry.revoked_at) == ("Joueur Un", "AAAAAAAAAAA", None)
    assert entry.created_at.startswith("2026-11-15T12:00:00")
    assert registry(tmp_path).entries() == [entry]


def test_mark_revoked_persists_and_only_touches_that_key(tmp_path: Path) -> None:
    store = registry(tmp_path)
    store.add("Un", "AAAAAAAAAAA")
    store.add("Deux", "BBBBBBBBBBB")
    store.mark_revoked("AAAAAAAAAAA")
    revoked = {entry.key_id: entry.revoked_at is not None for entry in registry(tmp_path).entries()}
    assert revoked == {"AAAAAAAAAAA": True, "BBBBBBBBBBB": False}


def test_marking_an_unknown_key_changes_nothing(tmp_path: Path) -> None:
    store = registry(tmp_path)
    store.add("Un", "AAAAAAAAAAA")
    store.mark_revoked("ZZZZZZZZZZZ")
    assert store.entries()[0].revoked_at is None


def test_the_file_never_contains_a_key_or_a_secret(tmp_path: Path) -> None:
    store = registry(tmp_path)
    store.add("Un", "AAAAAAAAAAA")
    assert "odk1." not in (tmp_path / "admin_keys.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("content", ["", "{pas du json", "[]", '"texte"', '{"keys": 5}', '{"keys": [1, "x", null]}',
                                     '{"keys": [{"key_id": 5, "label": "x"}]}',
                                     '{"keys": [{"key_id": "court", "label": "x", "created_at": "2026-11-15T12:00:00+00:00"}]}',
                                     '{"keys": [{"key_id": "ééééééééééé", "label": "x", "created_at": "2026-11-15T12:00:00+00:00"}]}'])
def test_absent_empty_corrupt_or_malformed_files_give_an_empty_list(tmp_path: Path, content: str) -> None:
    assert registry(tmp_path).entries() == []
    (tmp_path / "admin_keys.json").write_text(content, encoding="utf-8")
    assert registry(tmp_path).entries() == []


def test_malformed_items_are_skipped_but_good_ones_are_kept(tmp_path: Path) -> None:
    good = {"key_id": "AAAAAAAAAAA", "label": "Un", "created_at": "2026-11-15T12:00:00+00:00", "revoked_at": None}
    (tmp_path / "admin_keys.json").write_text(json.dumps({"keys": [5, good, {"label": "sans id"}]}), encoding="utf-8")
    assert [entry.label for entry in registry(tmp_path).entries()] == ["Un"]


def test_a_label_already_active_is_refused_but_a_revoked_one_can_be_reused(tmp_path: Path) -> None:
    store = registry(tmp_path)
    store.add("Joueur", "AAAAAAAAAAA")
    with pytest.raises(LabelExistsError):
        store.add("joueur", "BBBBBBBBBBB")
    store.mark_revoked("AAAAAAAAAAA")
    assert store.add("Joueur", "BBBBBBBBBBB").key_id == "BBBBBBBBBBB"


@pytest.mark.parametrize("text, expected", [("  Joueur  ", "Joueur"), ("A" * MAX_LABEL_LENGTH, "A" * MAX_LABEL_LENGTH),
                                            ("", None), ("   ", None), ("A" * (MAX_LABEL_LENGTH + 1), None),
                                            ("a\nb", None), ("a\x00b", None), ("a\tb", None)])
def test_clean_label(text: str, expected: str | None) -> None:
    assert clean_label(text) == expected
