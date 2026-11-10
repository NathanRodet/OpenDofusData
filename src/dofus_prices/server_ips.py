"""Game server addresses (public IPv4) mapped to server names: pure, no IO.

Only the game server's address is ever handled here. Addresses that cannot be a Dofus
server (private, loopback, link-local, multicast...) are refused: they may be the
player's own address, which must never be stored or logged.
"""

import ipaddress
import logging
from collections.abc import Mapping

logger = logging.getLogger(__name__)

BUNDLED_SERVER_IPS: dict[str, str] = {"99.81.217.174": "Kourial"}
IPS_KEY = "ips"
ORIGIN_BUNDLED = "livré"
ORIGIN_LEARNED = "appris"
INVALID_ADDRESS_MESSAGE = "adresse refusée : seule une adresse IPv4 publique peut être un serveur de jeu"
EMPTY_NAME_MESSAGE = "nom de serveur vide"
IGNORED_ENTRY_WARNING = "entrée « ips » ignorée dans la configuration (%s)"


def normalise_server_ip(text: object) -> str | None:
    """Return the canonical text of a public IPv4 address, or None if it cannot be a server."""
    if not isinstance(text, str):
        return None
    try:
        address = ipaddress.IPv4Address(text.strip())
    except ValueError:
        return None
    usable = address.is_global and not address.is_multicast
    return str(address) if usable else None


def _clean_learned(config_ips: object) -> dict[str, str]:
    """Keep the valid entries of the config table; warn (without the value) for the others."""
    if not isinstance(config_ips, Mapping):
        if config_ips is not None:
            logger.warning(IGNORED_ENTRY_WARNING, "objet attendu")
        return {}
    learned: dict[str, str] = {}
    for raw_address, server in config_ips.items():
        address = normalise_server_ip(raw_address)
        if address is not None and isinstance(server, str) and server.strip():
            learned[address] = server.strip()
        else:
            logger.warning(IGNORED_ENTRY_WARNING, "adresse ou nom invalide")
    return learned


class ServerIps:
    """Known server addresses: the bundled table plus the learned ones (which win)."""

    def __init__(self, config_ips: object = None) -> None:
        self._learned = _clean_learned(config_ips)

    def lookup(self, ip: str) -> str | None:
        """Return the server name of an address, or None when it is not known."""
        address = normalise_server_ip(ip)
        if address is None:
            return None
        return self._learned.get(address, BUNDLED_SERVER_IPS.get(address))

    def learn(self, ip: str, server: str) -> None:
        """Remember in memory that this server address belongs to this server."""
        address = normalise_server_ip(ip)
        if address is None:
            raise ValueError(INVALID_ADDRESS_MESSAGE)
        if not server.strip():
            raise ValueError(EMPTY_NAME_MESSAGE)
        self._learned[address] = server.strip()

    def forget(self, ip: str) -> bool:
        """Remove a learned address; return False when it was not learned."""
        address = normalise_server_ip(ip)
        return address is not None and self._learned.pop(address, None) is not None

    def to_config(self) -> dict[str, str]:
        """Return the learned entries only (the bundled ones are not saved)."""
        return dict(self._learned)

    def entries(self) -> list[tuple[str, str, str]]:
        """Return (address, server, origin) rows: learned first, then bundled not overridden."""
        rows = [(ip, server, ORIGIN_LEARNED) for ip, server in sorted(self._learned.items())]
        rows += [(ip, server, ORIGIN_BUNDLED) for ip, server in sorted(BUNDLED_SERVER_IPS.items())
                 if ip not in self._learned]
        return rows
