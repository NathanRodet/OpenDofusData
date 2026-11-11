"""Tests of the verified update download (fake fetcher, no network)."""

import hashlib
import urllib.request

import pytest

from opendofusdata.update_download import (
    AllowedRedirectHandler, UpdateError, download_update, http_get_bytes, parse_checksum,
)
from opendofusdata.updates import UpdateInfo

EXE_URL = "https://github.com/NathanRodet/OpenDofusData/releases/download/v1.1.0/OpenDofusData.exe"
CHECKSUM_URL = EXE_URL + ".sha256"
EXE_BYTES = b"MZ" + b"fake executable" * 100
GOOD_SUM = hashlib.sha256(EXE_BYTES).hexdigest()
MEGABYTE = 1024 * 1024


def info(exe_url: str | None = EXE_URL, checksum_url: str | None = CHECKSUM_URL) -> UpdateInfo:
    return UpdateInfo("1.1.0", "https://github.com/NathanRodet/OpenDofusData/releases/tag/v1.1.0",
                      exe_url, checksum_url)


class FakeFetcher:
    def __init__(self, checksum_text: str = f"{GOOD_SUM}  OpenDofusData.exe\n", exe: bytes = EXE_BYTES) -> None:
        self.calls: list[tuple[str, int]] = []
        self._answers = {CHECKSUM_URL: checksum_text.encode(), EXE_URL: exe}

    def __call__(self, url: str, max_bytes: int) -> bytes:
        self.calls.append((url, max_bytes))
        return self._answers[url]


def test_parse_checksum_reads_the_first_hex_token() -> None:
    assert parse_checksum(f"{GOOD_SUM}  file.exe\n") == GOOD_SUM
    assert parse_checksum(GOOD_SUM.upper()) == GOOD_SUM
    for bad in ("", "xyz", "abc123", GOOD_SUM[:-1], GOOD_SUM + "00"):
        assert parse_checksum(bad) is None


def test_a_verified_download_is_written_next_to_the_target(tmp_path) -> None:
    path = download_update(info(), tmp_path, FakeFetcher())
    assert path.parent == tmp_path
    assert path.read_bytes() == EXE_BYTES
    assert path.name.endswith(".new")
    assert "1.1.0" in path.name


def test_a_wrong_checksum_is_refused_and_leaves_no_file(tmp_path) -> None:
    with pytest.raises(UpdateError, match="somme de contrôle"):
        download_update(info(), tmp_path, FakeFetcher(checksum_text="0" * 64))
    assert list(tmp_path.iterdir()) == []


def test_an_unreadable_checksum_file_is_refused(tmp_path) -> None:
    with pytest.raises(UpdateError, match="somme de contrôle"):
        download_update(info(), tmp_path, FakeFetcher(checksum_text="not a checksum"))
    assert list(tmp_path.iterdir()) == []


def test_an_update_without_exe_or_checksum_cannot_be_downloaded(tmp_path) -> None:
    for incomplete in (info(exe_url=None), info(checksum_url=None)):
        with pytest.raises(UpdateError, match="pas installable"):
            download_update(incomplete, tmp_path, FakeFetcher())


def test_downloads_are_size_capped(tmp_path) -> None:
    fetcher = FakeFetcher()
    download_update(info(), tmp_path, fetcher)
    sizes = dict(fetcher.calls)
    assert sizes[CHECKSUM_URL] <= 4096
    assert sizes[EXE_URL] <= 200 * MEGABYTE


def test_a_previous_partial_file_is_replaced(tmp_path) -> None:
    target = tmp_path / "OpenDofusData-1.1.0.exe.new"
    target.write_bytes(b"old partial")
    assert download_update(info(), tmp_path, FakeFetcher()).read_bytes() == EXE_BYTES


def test_redirects_to_foreign_hosts_are_refused_and_github_ones_followed() -> None:
    handler = AllowedRedirectHandler()
    request = urllib.request.Request(EXE_URL)
    with pytest.raises(UpdateError, match="refusée"):
        handler.redirect_request(request, None, 302, "Found", {}, "https://evil.example/O.exe")
    followed = handler.redirect_request(
        request, None, 302, "Found", {}, "https://objects.githubusercontent.com/release/O.exe")
    assert followed.full_url == "https://objects.githubusercontent.com/release/O.exe"


def test_http_get_bytes_refuses_a_foreign_host_before_any_request() -> None:
    with pytest.raises(UpdateError, match="refusée"):
        http_get_bytes("https://evil.example/O.exe", 10)
