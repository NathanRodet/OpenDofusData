"""Update logic: version comparison and reading a GitHub release (pure, no network)."""

import re
from dataclasses import dataclass
from urllib.parse import urlparse


EXE_ASSET_NAME = "OpenDofusData.exe"
CHECKSUM_ASSET_NAME = "OpenDofusData.exe.sha256"
ALLOWED_HOSTS = frozenset({
    "github.com", "api.github.com", "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
})
HTTPS_SCHEME = "https"
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

Version = tuple[int, int, int]


@dataclass(frozen=True)
class UpdateInfo:
    """A newer release; the executable and its checksum may be absent (then: open the page)."""

    version: str
    page_url: str
    exe_url: str | None
    checksum_url: str | None

    @property
    def can_install(self) -> bool:
        """True when the executable and its checksum are both published."""
        return self.exe_url is not None and self.checksum_url is not None


def parse_version(text: str) -> Version | None:
    """'1.2.3' or 'v1.2.3' as numbers; None for anything else."""
    match = VERSION_PATTERN.match(text) if isinstance(text, str) else None
    return None if match is None else (int(match[1]), int(match[2]), int(match[3]))


def is_newer(candidate: str, current: str) -> bool:
    """True when `candidate` is a strictly higher version than `current` (both must parse)."""
    candidate_version, current_version = parse_version(candidate), parse_version(current)
    return candidate_version is not None and current_version is not None and candidate_version > current_version


def is_allowed_url(url: str) -> bool:
    """HTTPS on a GitHub host only (what the tool may open or download)."""
    parsed = urlparse(url) if isinstance(url, str) else None
    return parsed is not None and parsed.scheme == HTTPS_SCHEME and parsed.hostname in ALLOWED_HOSTS


def _asset_url(assets: object, name: str) -> str | None:
    for asset in assets if isinstance(assets, list) else []:
        if isinstance(asset, dict) and asset.get("name") == name:
            url = asset.get("browser_download_url")
            return url if is_allowed_url(url) else None
    return None


def find_update(release: object, current_version: str) -> UpdateInfo | None:
    """Read a GitHub 'latest release' payload; None unless it is a newer published release."""
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    tag, page_url = release.get("tag_name"), release.get("html_url")
    if not isinstance(tag, str) or not is_newer(tag, current_version) or not is_allowed_url(page_url):
        return None
    assets = release.get("assets")
    return UpdateInfo(tag.lstrip("v"), page_url, _asset_url(assets, EXE_ASSET_NAME),
                      _asset_url(assets, CHECKSUM_ASSET_NAME))

