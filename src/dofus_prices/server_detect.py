"""Resolves the server of a flow from its game server address: pure, callables injected."""

import logging
from collections.abc import Callable

from dofus_prices.capture import server_ip_of
from dofus_prices.game_servers import UNKNOWN_SERVER
from dofus_prices.server_ips import ServerIps, normalise_server_ip
from dofus_prices.tcp import FlowKey

logger = logging.getLogger(__name__)

Persist = Callable[[dict[str, str]], None]
Say = Callable[[str], None]

LEARNED_MESSAGE = "adresse du serveur de jeu {ip} associée à « {server} »"
UNKNOWN_ADDRESS_MESSAGE = (
    "Adresse de serveur inconnue ({ip}): relevés marqués « unknown ». "
    r"Lance `.\dev.ps1 capture --choose-server` ou `.\dev.ps1 run server --learn NOM` "
    "quand tu es connecté.")
SAVE_WARNING = "Adresse du serveur non mémorisée : écriture de la configuration impossible (%s)"


class ServerResolver:
    """Gives the server of each flow: known address, else learned once, else `unknown`."""

    def __init__(self, ips: ServerIps, session_server: str, explicit: bool,
                 persist: Persist, say: Say) -> None:
        self._ips = ips
        self._session_server = session_server
        self._explicit = explicit
        self._persist = persist
        self._say = say
        self._warned: set[str] = set()

    def __call__(self, key: FlowKey) -> str:
        """Return the server name for a flow (never guesses from a remembered choice)."""
        address = normalise_server_ip(server_ip_of(key))
        if address is None:
            return self._session_server
        known = self._ips.lookup(address)
        if known is not None:
            return known
        if self._explicit and self._session_server != UNKNOWN_SERVER:
            return self._learn(address)
        self._warn_once(address)
        return UNKNOWN_SERVER

    def _learn(self, address: str) -> str:
        self._ips.learn(address, self._session_server)
        try:
            self._persist(self._ips.to_config())
        except OSError as error:
            logger.warning(SAVE_WARNING, error)
        self._say(LEARNED_MESSAGE.format(ip=address, server=self._session_server))
        return self._session_server

    def _warn_once(self, address: str) -> None:
        if address not in self._warned:
            self._warned.add(address)
            self._say(UNKNOWN_ADDRESS_MESSAGE.format(ip=address))
