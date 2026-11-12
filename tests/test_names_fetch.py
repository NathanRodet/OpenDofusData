"""Tests for the DofusDB download, with a fake HTTP function (no network)."""

import csv
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from opendofusdata import names_build, names_fetch
from opendofusdata.names_fetch import (
    NamesFetchError,
    TransientFetchError,
    download_item_names,
)

TYPES = [{"id": 1, "name": {"fr": "Amulette"}}, {"id": 2, "name": {"fr": "Arc"}}]
ITEMS = [
    {"id": 376, "typeId": 2, "level": 20, "name": {"fr": "Aile du Tofu Maléfique", "en": "Tofu wing"}},
    {"id": 307, "typeId": 1, "level": 1, "name": {"fr": "Ailes de Moskito"}},
    {"id": 5, "typeId": 1, "level": 3, "name": {"en": "English only"}},
    {"id": 6, "typeId": 1, "level": 3, "name": {}},
    {"id": 7, "typeId": 9, "level": 4, "name": {"fr": "Faux\x00 \n  nom\x07"}},
]
PAGE_SIZE_FOR_TESTS = 2


class FakeApi:
    """Serves paginated JSON like DofusDB and records the requested URLs."""

    def __init__(self, items=ITEMS, types=TYPES, total_shift: int = 0) -> None:
        self.urls: list[str] = []
        self._collections = {"/items": items, "/item-types": types}
        self._total_shift = total_shift
        self.failures: list[Exception] = []

    def __call__(self, url: str) -> object:
        self.urls.append(url)
        if self.failures:
            raise self.failures.pop(0)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        rows = self._collections[parsed.path]
        skip, limit = int(query["$skip"][0]), int(query["$limit"][0])
        return {"total": len(rows) + self._total_shift, "limit": limit, "skip": skip,
                "data": rows[skip:skip + limit]}


def run_download(output: Path, fetch, messages: list[str] | None = None, sleeps: list[float] | None = None):
    return download_item_names(
        output, fetch=fetch, page_size=PAGE_SIZE_FOR_TESTS, request_delay=0.0,
        sleep=(sleeps if sleeps is not None else []).append,
        progress=(messages if messages is not None else []).append,
    )


def read_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.reader(file))


def test_download_writes_sorted_csv_with_header(tmp_path: Path) -> None:
    output = tmp_path / "data" / "items.csv"
    summary = run_download(output, FakeApi())
    rows = read_rows(output)
    assert rows[0] == ["id", "name_fr", "level", "type_fr", "recycling_nuggets"]
    assert rows[1:] == [["5", "English only", "3", "Amulette", ""], ["7", "Faux nom", "4", "", ""],
                        ["307", "Ailes de Moskito", "1", "Amulette", ""],
                        ["376", "Aile du Tofu Maléfique", "20", "Arc", ""]]
    assert (summary.rows, summary.skipped, summary.path) == (4, 1, output)
    assert summary.size_bytes == output.stat().st_size


def test_download_pages_through_every_collection(tmp_path: Path) -> None:
    api = FakeApi()
    run_download(tmp_path / "items.csv", api)
    skips = [(urlparse(url).path, parse_qs(urlparse(url).query)["$skip"][0]) for url in api.urls]
    assert skips == [("/item-types", "0"), ("/items", "0"), ("/items", "2"), ("/items", "4")]


def test_duplicate_id_keeps_the_first_row(tmp_path: Path) -> None:
    items = [*ITEMS[:2], {"id": 307, "typeId": 2, "level": 9, "name": {"fr": "Doublon"}}]
    summary = run_download(tmp_path / "items.csv", FakeApi(items=items))
    assert [row[:2] for row in read_rows(tmp_path / "items.csv")[1:]] == [
        ["307", "Ailes de Moskito"], ["376", "Aile du Tofu Maléfique"]]
    assert summary.duplicates == 1


def test_names_are_sanitised_and_capped(tmp_path: Path) -> None:
    items = [{"id": 1, "typeId": 1, "level": 1, "name": {"fr": "x" * 500}}]
    run_download(tmp_path / "items.csv", FakeApi(items=items))
    assert len(read_rows(tmp_path / "items.csv")[1][1]) == names_build.MAX_NAME_LENGTH


def test_total_mismatch_is_an_error_and_leaves_no_file(tmp_path: Path) -> None:
    with pytest.raises(NamesFetchError, match="attendu"):
        run_download(tmp_path / "items.csv", FakeApi(total_shift=1))
    assert list(tmp_path.iterdir()) == []


def test_unexpected_shape_is_a_french_error(tmp_path: Path) -> None:
    for payload in ({"hello": 1}, ["x"]):
        with pytest.raises(NamesFetchError, match="inattendue"):
            run_download(tmp_path / "items.csv", lambda url: payload)
    assert list(tmp_path.iterdir()) == []


def test_item_without_integer_id_is_an_unexpected_shape(tmp_path: Path) -> None:
    items = [{"id": "x", "name": {"fr": "Y"}}]
    with pytest.raises(NamesFetchError, match="inattendue"):
        run_download(tmp_path / "items.csv", FakeApi(items=items))


def test_transient_error_is_retried_with_backoff(tmp_path: Path) -> None:
    api, sleeps = FakeApi(), []
    api.failures = [TransientFetchError("HTTP 429"), TransientFetchError("HTTP 503")]
    run_download(tmp_path / "items.csv", api, sleeps=sleeps)
    assert sleeps == [names_fetch.RETRY_BACKOFF_SECONDS, names_fetch.RETRY_BACKOFF_SECONDS * 2]
    assert len(read_rows(tmp_path / "items.csv")) == 5


def test_persistent_failure_is_a_french_error_without_file(tmp_path: Path) -> None:
    api = FakeApi()
    api.failures = [TransientFetchError("HTTP 503")] * 20
    with pytest.raises(NamesFetchError, match="échec"):
        run_download(tmp_path / "items.csv", api)
    assert len(api.urls) == names_fetch.MAX_ATTEMPTS
    assert list(tmp_path.iterdir()) == []


def test_failure_midway_keeps_the_previous_file_and_no_temp(tmp_path: Path) -> None:
    output = tmp_path / "items.csv"
    output.write_text("previous", encoding="utf-8")
    api = FakeApi()

    def fail_on_third_page(url: str) -> object:
        if len(api.urls) == 2:
            raise NamesFetchError("boom")
        return api(url)

    with pytest.raises(NamesFetchError):
        run_download(output, fail_on_third_page)
    assert [path.name for path in tmp_path.iterdir()] == ["items.csv"]
    assert output.read_text(encoding="utf-8") == "previous"


def test_failed_rename_leaves_no_temp_file(tmp_path: Path, monkeypatch) -> None:
    def refuse(source, destination) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr("opendofusdata.names_build.os.replace", refuse)
    with pytest.raises(NamesFetchError, match="écrire"):
        run_download(tmp_path / "items.csv", FakeApi())
    assert list(tmp_path.iterdir()) == []


def test_progress_is_reported_every_twenty_pages(tmp_path: Path) -> None:
    items = [{"id": number, "typeId": 1, "level": 1, "name": {"fr": f"N{number}"}} for number in range(1, 61)]
    messages: list[str] = []
    run_download(tmp_path / "items.csv", FakeApi(items=items), messages=messages)
    assert len(messages) == 1 and "20/30" in messages[0] and "pages" in messages[0]


def test_delay_is_applied_between_requests(tmp_path: Path) -> None:
    sleeps: list[float] = []
    download_item_names(tmp_path / "items.csv", fetch=FakeApi(), page_size=PAGE_SIZE_FOR_TESTS,
                        request_delay=0.5, sleep=sleeps.append, progress=lambda text: None)
    assert sleeps and set(sleeps) == {0.5}
