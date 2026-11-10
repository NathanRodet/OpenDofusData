"""Parses the text of Windows `netstat -n -p tcp` (English or French): pure, no IO."""

from dofus_prices.capture import DOFUS_PORT
from dofus_prices.server_ips import normalise_server_ip

MIN_COLUMNS = 4
TCP_PROTOCOL = "TCP"
ESTABLISHED_STATES = ("ESTABLISHED",)
FRENCH_ESTABLISHED_SUFFIX = "TABLI"  # ÉTABLI, whatever the console codepage did to the accent
FRENCH_ESTABLISHED_LENGTH = len("ÉTABLI")


def _is_established(state: str) -> bool:
    upper = state.upper()
    return upper in ESTABLISHED_STATES or (
        len(upper) == FRENCH_ESTABLISHED_LENGTH and upper.endswith(FRENCH_ESTABLISHED_SUFFIX))


def _remote_game_address(remote: str) -> str | None:
    """Return the validated IPv4 of a `host:5555` endpoint, else None (IPv6 included)."""
    host, separator, port = remote.rpartition(":")
    if not separator or port != str(DOFUS_PORT):
        return None
    return normalise_server_ip(host)


def _address_of_line(line: str) -> str | None:
    columns = line.split()
    if len(columns) < MIN_COLUMNS or columns[0].upper() != TCP_PROTOCOL:
        return None
    if not _is_established(columns[3]):
        return None
    return _remote_game_address(columns[2])


def parse_netstat(text: str) -> list[str]:
    """Return the distinct server addresses of established connections to the game port."""
    addresses: list[str] = []
    for line in text.splitlines():
        address = _address_of_line(line)
        if address is not None and address not in addresses:
            addresses.append(address)
    return addresses
