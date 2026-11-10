"""Tests for the learned server address table and server_ip_of (pure, no network)."""

import logging

import pytest

from dofus_prices.capture import server_ip_of
from dofus_prices.server_ips import BUNDLED_SERVER_IPS, ServerIps, normalise_server_ip

KOURIAL_IP = "99.81.217.174"
OTHER_IP = "52.17.4.9"
PLAYER_IP = "192.168.1.20"
NOT_SERVER_ADDRESSES = ["10.0.0.5", "192.168.1.20", "172.16.0.1", "127.0.0.1", "169.254.3.4",
                        "224.0.0.1", "0.0.0.0", "100.64.0.1", "::1", "2001:db8::1",
                        "not an ip", "", "999.1.1.1", "1.2.3"]


def test_bundle_contains_kourial() -> None:
    assert BUNDLED_SERVER_IPS == {KOURIAL_IP: "Kourial"}
    assert ServerIps().lookup(KOURIAL_IP) == "Kourial"
    assert ServerIps().lookup(OTHER_IP) is None


def test_config_ips_are_known_and_override_the_bundle() -> None:
    ips = ServerIps({OTHER_IP: "Brial", KOURIAL_IP: "Autre"})
    assert ips.lookup(OTHER_IP) == "Brial"
    assert ips.lookup(KOURIAL_IP) == "Autre"


def test_learn_is_in_memory_and_reported_by_to_config() -> None:
    ips = ServerIps()
    assert ips.to_config() == {}
    ips.learn(OTHER_IP, "Brial")
    assert ips.lookup(OTHER_IP) == "Brial"
    assert ips.to_config() == {OTHER_IP: "Brial"}


def test_forget_removes_only_learned_entries() -> None:
    ips = ServerIps({OTHER_IP: "Brial"})
    assert ips.forget(OTHER_IP) is True and ips.lookup(OTHER_IP) is None
    assert ips.forget(KOURIAL_IP) is False and ips.lookup(KOURIAL_IP) == "Kourial"


def test_entries_list_bundled_and_learned_with_origin() -> None:
    ips = ServerIps({OTHER_IP: "Brial"})
    assert ips.entries() == [(OTHER_IP, "Brial", "appris"), (KOURIAL_IP, "Kourial", "livré")]


@pytest.mark.parametrize("address", NOT_SERVER_ADDRESSES)
def test_private_loopback_ipv6_and_garbage_are_rejected(address: str) -> None:
    assert normalise_server_ip(address) is None
    ips = ServerIps()
    with pytest.raises(ValueError) as error:
        ips.learn(address, "Kourial")
    assert address == "" or address not in str(error.value)
    assert ips.to_config() == {} and ips.lookup(address) is None


def test_learn_rejects_an_empty_server_name() -> None:
    with pytest.raises(ValueError):
        ServerIps().learn(OTHER_IP, "  ")


def test_corrupt_config_entries_are_ignored_with_a_warning_without_the_value(caplog) -> None:
    caplog.set_level(logging.WARNING)
    ips = ServerIps({PLAYER_IP: "Brial", "junk": "X", OTHER_IP: 5, "52.17.4.10": "Ok"})
    assert ips.to_config() == {"52.17.4.10": "Ok"}
    assert len(caplog.records) == 3
    assert PLAYER_IP not in caplog.text and "junk" not in caplog.text


@pytest.mark.parametrize("config_ips", [None, [], "x", 3])
def test_config_ips_of_the_wrong_type_are_ignored(config_ips: object) -> None:
    assert ServerIps(config_ips).to_config() == {}


def test_server_ip_of_returns_the_game_port_endpoint_only() -> None:
    assert server_ip_of((KOURIAL_IP, 5555, PLAYER_IP, 40000)) == KOURIAL_IP
    assert server_ip_of((PLAYER_IP, 40000, KOURIAL_IP, 5555)) == KOURIAL_IP
    assert server_ip_of((PLAYER_IP, 40000, KOURIAL_IP, 443)) is None
