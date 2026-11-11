"""Tests for the safety limits and interruption handling of the names download."""

from pathlib import Path

import pytest

from opendofusdata import names_build, names_fetch
from opendofusdata.names_fetch import NamesFetchError
from tests.test_names_fetch import PAGE_SIZE_FOR_TESTS, FakeApi, run_download


def test_total_above_the_cap_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(names_fetch, "MAX_COLLECTION_ITEMS", 3)
    items = [{"id": number, "name": {"fr": "N"}} for number in range(1, 5)]
    with pytest.raises(NamesFetchError, match="trop"):
        run_download(tmp_path / "items.csv", FakeApi(items=items))
    assert list(tmp_path.iterdir()) == []


def test_more_items_than_the_total_stops_with_an_error(tmp_path: Path) -> None:
    def overflowing(url: str) -> object:
        return {"total": 1, "data": [{"id": 1, "name": {"fr": "A"}}, {"id": 2, "name": {"fr": "B"}}]}

    with pytest.raises(NamesFetchError, match="attendus"):
        run_download(tmp_path / "items.csv", overflowing)
    assert list(tmp_path.iterdir()) == []


def test_keyboard_interrupt_during_the_write_leaves_no_temp_and_keeps_the_old_file(
        tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "items.csv"
    output.write_text("previous", encoding="utf-8")

    def interrupted(file, entries) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(names_build, "_write_rows", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_download(output, FakeApi())
    assert [path.name for path in tmp_path.iterdir()] == ["items.csv"]
    assert output.read_text(encoding="utf-8") == "previous"


def test_endless_one_item_pages_hit_the_page_limit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(names_fetch, "MAX_COLLECTION_ITEMS", 10)
    requested: list[str] = []

    def endless(url: str) -> object:
        requested.append(url)
        return {"total": 10, "data": [{"id": len(requested), "name": {"fr": "N"}}]}

    with pytest.raises(NamesFetchError, match="pages"):
        run_download(tmp_path / "items.csv", endless)
    assert len(requested) <= 10 // PAGE_SIZE_FOR_TESTS + 2 + 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("total", [-1, 2.5, "10", True, None])
def test_invalid_total_is_an_unexpected_shape(tmp_path: Path, total) -> None:
    def odd(url: str) -> object:
        return {"total": total, "data": [{"id": 1, "name": {"fr": "N"}}]}

    with pytest.raises(NamesFetchError, match="inattendue"):
        run_download(tmp_path / "items.csv", odd)
    assert list(tmp_path.iterdir()) == []
