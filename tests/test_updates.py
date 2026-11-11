"""Tests of the update logic: version comparison and reading a GitHub release (no network)."""

import pytest

from opendofusdata.updates import (
    CHECKSUM_ASSET_NAME, EXE_ASSET_NAME, find_update, is_allowed_url, is_newer, parse_version,
)

RELEASE_PAGE = "https://github.com/NathanRodet/OpenDofusData/releases/tag/v1.1.0"
EXE_URL = "https://github.com/NathanRodet/OpenDofusData/releases/download/v1.1.0/OpenDofusData.exe"
CHECKSUM_URL = EXE_URL + ".sha256"


def release(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "tag_name": "v1.1.0", "draft": False, "prerelease": False, "html_url": RELEASE_PAGE,
        "assets": [{"name": EXE_ASSET_NAME, "browser_download_url": EXE_URL},
                   {"name": CHECKSUM_ASSET_NAME, "browser_download_url": CHECKSUM_URL}],
    }
    return {**base, **overrides}


@pytest.mark.parametrize("text, expected", [
    ("1.2.3", (1, 2, 3)), ("v1.2.3", (1, 2, 3)), ("10.0.12", (10, 0, 12)),
    ("1.2", None), ("1.2.3.4", None), ("1.2.x", None), ("", None), ("v", None), (" 1.2.3 ", None),
])
def test_parse_version(text: str, expected) -> None:
    assert parse_version(text) == expected


def test_is_newer_compares_numbers_not_text() -> None:
    assert is_newer("1.10.0", "1.9.0")
    assert is_newer("2.0.0", "1.99.99")
    assert not is_newer("1.0.0", "1.0.0")
    assert not is_newer("0.9.0", "1.0.0")
    assert not is_newer("garbage", "1.0.0")
    assert not is_newer("1.1.0", "garbage")


def test_a_newer_release_gives_an_installable_update() -> None:
    update = find_update(release(), "1.0.0")
    assert update is not None
    assert (update.version, update.page_url, update.exe_url, update.checksum_url) == (
        "1.1.0", RELEASE_PAGE, EXE_URL, CHECKSUM_URL)
    assert update.can_install is True


def test_the_same_or_an_older_release_gives_no_update() -> None:
    assert find_update(release(), "1.1.0") is None
    assert find_update(release(), "2.0.0") is None


@pytest.mark.parametrize("payload", [
    None, [], "text", {}, {"tag_name": 5}, release(tag_name="latest"), release(draft=True),
    release(prerelease=True), release(html_url="http://github.com/x"), release(html_url=7),
    release(html_url="https://evil.example/releases"),
])
def test_unusable_releases_are_ignored(payload: object) -> None:
    assert find_update(payload, "1.0.0") is None


def test_a_release_without_the_exe_announces_the_version_but_cannot_be_installed() -> None:
    update = find_update(release(assets=[]), "1.0.0")
    assert update is not None
    assert update.exe_url is None
    assert update.can_install is False


def test_a_release_without_checksum_cannot_be_installed() -> None:
    assets = [{"name": EXE_ASSET_NAME, "browser_download_url": EXE_URL}]
    update = find_update(release(assets=assets), "1.0.0")
    assert update is not None
    assert update.checksum_url is None
    assert update.can_install is False


def test_assets_with_foreign_hosts_are_dropped() -> None:
    assets = [{"name": EXE_ASSET_NAME, "browser_download_url": "https://evil.example/OpenDofusData.exe"},
              {"name": CHECKSUM_ASSET_NAME, "browser_download_url": CHECKSUM_URL},
              "not a dict", {"name": 3}]
    update = find_update(release(assets=assets), "1.0.0")
    assert update is not None
    assert update.exe_url is None


def test_allowed_urls_are_https_on_github_hosts_only() -> None:
    assert is_allowed_url("https://github.com/a/b")
    assert is_allowed_url("https://objects.githubusercontent.com/x?y=1")
    assert not is_allowed_url("http://github.com/a/b")
    assert not is_allowed_url("https://github.com.evil.example/a")
    assert not is_allowed_url("https://evil.example/github.com")
    assert not is_allowed_url("ftp://github.com/a")
    assert not is_allowed_url("")
