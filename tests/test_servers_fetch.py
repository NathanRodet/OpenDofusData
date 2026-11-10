"""Tests for the game servers download and CSV, with a fake HTTP function (no network)."""

import csv
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from dofus_prices import names_build, servers_build
from dofus_prices.names_fetch import NamesFetchError, TransientFetchError
from dofus_prices.servers_fetch import download_game_servers
from tests.test_names_fetch import FakeApi

GAME_TYPES = [{"id": 0, "name": {"fr": "Classique"}}, {"id": 3, "name": {"fr": "Tournoi"}}]
SERVERS = [
    {"id": 293, "name": {"fr": "Tylezia", "en": "Tylezia"}, "gameTypeId": 0, "communityId": 2},
    {"id": 291, "name": {"fr": "Imagiro"}, "gameTypeId": 0, "communityId": 0},
    {"id": 900, "name": {"fr": "Speed\x00 \n Rush"}, "gameTypeId": 3, "communityId": 1},
    {"id": 901, "name": {"fr": "[!] Marqué"}, "gameTypeId": 77, "communityId": 1},
    {"id": 902, "name": {"fr": "\x07", "en": "English only"}, "gameTypeId": 0},
    {"id": 903, "name": {"fr": "\x07"}, "gameTypeId": 0, "communityId": 0},
    {"id": 291, "name": {"fr": "Doublon"}, "gameTypeId": 0, "communityId": 0},
]
PAGE_SIZE_FOR_TESTS = 2


class FakeServersApi(FakeApi):
    """Serves the two server collections like DofusDB."""

    def __init__(self, servers=SERVERS, types=GAME_TYPES, total_shift: int = 0) -> None:
        super().__init__(total_shift=total_shift)
        self._collections = {"/servers": servers, "/server-game-types": types}


def run_download(output: Path, fetch, sleeps: list[float] | None = None, **options):
    return download_game_servers(
        output, fetch=fetch, page_size=PAGE_SIZE_FOR_TESTS, request_delay=0.0, **options,
        sleep=(sleeps if sleeps is not None else []).append, progress=[].append)


def read_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.reader(file))


def test_download_with_all_writes_every_server_sorted_with_resolved_game_types(tmp_path: Path) -> None:
    output = tmp_path / "data" / "servers.csv"
    summary = run_download(output, FakeServersApi(), classic_only=False)
    rows = read_rows(output)
    assert rows[0] == ["id", "name_fr", "game_type_id", "game_type_fr", "community_id"]
    assert rows[1:] == [["291", "Imagiro", "0", "Classique", "0"],
                        ["293", "Tylezia", "0", "Classique", "2"],
                        ["900", "Speed Rush", "3", "Tournoi", "1"],
                        ["901", "[!] Marqué", "77", "", "1"],
                        ["902", "English only", "0", "Classique", ""]]
    assert (summary.rows, summary.skipped, summary.duplicates) == (5, 1, 1)
    assert (summary.received, summary.excluded) == (7, 0)
    assert summary.path == output and summary.size_bytes == output.stat().st_size


def test_download_keeps_only_classic_servers_by_default(tmp_path: Path) -> None:
    output = tmp_path / "servers.csv"
    summary = run_download(output, FakeServersApi())
    assert [row[0] for row in read_rows(output)[1:]] == ["291", "293", "902"]
    assert {row[2] for row in read_rows(output)[1:]} == {"0"}
    assert (summary.rows, summary.received, summary.excluded) == (3, 7, 2)


def test_total_check_counts_the_rows_received_before_the_classic_filter(tmp_path: Path) -> None:
    with pytest.raises(NamesFetchError):
        run_download(tmp_path / "servers.csv", FakeServersApi(total_shift=1))
    assert list(tmp_path.iterdir()) == []


def test_download_requests_types_then_servers_page_by_page(tmp_path: Path) -> None:
    api = FakeServersApi()
    run_download(tmp_path / "servers.csv", api)
    seen = [(urlparse(url).path, parse_qs(urlparse(url).query)["$skip"][0]) for url in api.urls]
    assert seen[0] == ("/server-game-types", "0")
    assert seen[1:] == [("/servers", str(skip)) for skip in (0, 2, 4, 6)]


def test_total_mismatch_fails_and_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(NamesFetchError):
        run_download(tmp_path / "servers.csv", FakeServersApi(total_shift=1))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("payload", [[], {"data": []}, {"total": 1, "data": "x"}, "text"])
def test_unexpected_shape_fails(tmp_path: Path, payload: object) -> None:
    with pytest.raises(NamesFetchError):
        run_download(tmp_path / "servers.csv", lambda url: payload)
    assert list(tmp_path.iterdir()) == []


def test_transient_failure_is_retried_then_succeeds(tmp_path: Path) -> None:
    api = FakeServersApi()
    api.failures = [TransientFetchError("HTTP 503")]
    sleeps: list[float] = []
    assert run_download(tmp_path / "servers.csv", api, sleeps).rows == 3
    assert sleeps and sleeps[0] > 0


def test_failure_keeps_an_existing_good_file(tmp_path: Path) -> None:
    output = tmp_path / "servers.csv"
    run_download(output, FakeServersApi())
    before = output.read_bytes()
    with pytest.raises(NamesFetchError):
        run_download(output, FakeServersApi(total_shift=3))
    assert output.read_bytes() == before
    assert [path.name for path in tmp_path.iterdir()] == ["servers.csv"]


def test_write_failure_leaves_no_temporary_file(tmp_path: Path, monkeypatch) -> None:
    def broken(source: str, destination: Path) -> None:
        raise OSError("disque plein")

    monkeypatch.setattr(names_build.os, "replace", broken)
    with pytest.raises(NamesFetchError):
        servers_build.write_servers_csv([], tmp_path / "servers.csv")
    assert list(tmp_path.iterdir()) == []
