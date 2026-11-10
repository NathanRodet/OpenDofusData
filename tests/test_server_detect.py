"""Tests for the server resolver rules (a)-(d): learned address, explicit, remembered, no IP."""

import logging

import pytest

from dofus_prices.server_detect import ServerResolver
from dofus_prices.server_ips import ServerIps

KOURIAL_IP = "99.81.217.174"
NEW_IP = "52.17.4.9"
PLAYER_IP = "192.168.1.20"
KOURIAL_KEY = (KOURIAL_IP, 5555, PLAYER_IP, 40000)
NEW_KEY = (NEW_IP, 5555, PLAYER_IP, 40001)
NO_GAME_PORT_KEY = ("1.2.3.4", 80, PLAYER_IP, 40002)
LOOPBACK_KEY = ("127.0.0.1", 5555, "127.0.0.1", 40003)


class Harness:
    """A resolver with recording persist and say callables."""

    def __init__(self, session: str, explicit: bool, fail_save: bool = False) -> None:
        self.ips = ServerIps()
        self.said: list[str] = []
        self.saved: list[dict[str, str]] = []
        self.fail_save = fail_save
        self.resolver = ServerResolver(self.ips, session, explicit, self.persist, self.said.append)

    def persist(self, learned: dict[str, str]) -> None:
        if self.fail_save:
            raise OSError("read-only")
        self.saved.append(dict(learned))


def test_rule_a_known_address_gives_its_server_whatever_the_session() -> None:
    for explicit in (True, False):
        harness = Harness("Brial", explicit)
        assert harness.resolver(KOURIAL_KEY) == "Kourial"
        assert harness.said == [] and harness.saved == []


def test_rule_a_uses_the_server_side_endpoint_in_both_directions() -> None:
    harness = Harness("Brial", False)
    assert harness.resolver((PLAYER_IP, 40000, KOURIAL_IP, 5555)) == "Kourial"


def test_rule_b_explicit_server_learns_persists_and_announces_once() -> None:
    harness = Harness("Brial", True)
    assert harness.resolver(NEW_KEY) == "Brial"
    assert harness.resolver(NEW_KEY) == "Brial"
    assert harness.ips.lookup(NEW_IP) == "Brial"
    assert harness.saved == [{NEW_IP: "Brial"}]
    assert harness.said == [f"adresse du serveur de jeu {NEW_IP} associée à « Brial »"]


def test_rule_b_never_prints_or_stores_the_player_address() -> None:
    harness = Harness("Brial", True)
    harness.resolver(NEW_KEY)
    assert PLAYER_IP not in " ".join(harness.said) + str(harness.saved)


def test_rule_b_does_not_learn_the_unknown_placeholder() -> None:
    harness = Harness("unknown", True)
    assert harness.resolver(NEW_KEY) == "unknown"
    assert harness.saved == [] and harness.ips.lookup(NEW_IP) is None


def test_rule_b_failed_save_only_warns_and_the_capture_goes_on(caplog) -> None:
    caplog.set_level(logging.WARNING)
    harness = Harness("Brial", True, fail_save=True)
    assert harness.resolver(NEW_KEY) == "Brial"
    assert harness.ips.lookup(NEW_IP) == "Brial"
    assert any("non mémorisée" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("session", ["Brial", "unknown"])
def test_rule_c_remembered_or_default_server_is_never_guessed(session: str) -> None:
    harness = Harness(session, False)
    assert harness.resolver(NEW_KEY) == "unknown"
    assert harness.ips.to_config() == {} and harness.saved == []


def test_rule_c_warns_once_per_address_in_french() -> None:
    harness = Harness("Brial", False)
    other_key = ("52.17.4.10", 5555, PLAYER_IP, 40001)
    for key in (NEW_KEY, NEW_KEY, other_key, NEW_KEY):
        harness.resolver(key)
    assert len(harness.said) == 2
    assert harness.said[0].startswith(f"Adresse de serveur inconnue ({NEW_IP}): relevés marqués")
    assert "--choose-server" in harness.said[0] and "server --learn NOM" in harness.said[0]
    assert PLAYER_IP not in " ".join(harness.said)


def test_rule_d_no_game_port_uses_the_session_server() -> None:
    assert Harness("Brial", True).resolver(NO_GAME_PORT_KEY) == "Brial"
    assert Harness("Brial", False).resolver(NO_GAME_PORT_KEY) == "Brial"
    assert Harness("unknown", False).resolver(NO_GAME_PORT_KEY) == "unknown"


def test_a_loopback_game_endpoint_is_treated_as_no_address() -> None:
    harness = Harness("Brial", True)
    assert harness.resolver(LOOPBACK_KEY) == "Brial"
    assert harness.ips.to_config() == {} and harness.saved == [] and harness.said == []
