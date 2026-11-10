"""Tests for the pure netstat parser on realistic Windows outputs."""

from dofus_prices.netstat_parse import parse_netstat

ENGLISH = """
Active Connections

  Proto  Local Address          Foreign Address        State
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING
  TCP    192.168.1.20:49822     99.81.217.174:5555     ESTABLISHED
  TCP    192.168.1.20:49830     52.17.4.9:443          ESTABLISHED
  TCP    192.168.1.20:49833     99.81.217.174:5555     TIME_WAIT
  TCP    192.168.1.20:49840     52.17.4.9:5555         ESTABLISHED
  TCP    192.168.1.20:49841     52.17.4.9:5555         ESTABLISHED
  TCP    [::1]:49700            [::1]:5555             ESTABLISHED
  TCP    [2001:db8::2]:49701    [2001:db8::9]:5555     ESTABLISHED
  TCP    127.0.0.1:49702        127.0.0.1:5555         ESTABLISHED
  TCP    192.168.1.20:49703     10.0.0.7:5555          ESTABLISHED
  TCP    192.168.1.20:5555      8.8.8.8:50000          ESTABLISHED
"""
FRENCH = """
Connexions actives

  Proto  Adresse locale         Adresse distante       État
  TCP    0.0.0.0:445            0.0.0.0:0              LISTENING
  TCP    192.168.1.20:49822     99.81.217.174:5555     ÉTABLI
  TCP    192.168.1.20:49833     99.81.217.174:5555     ATTENTE
  TCP    [fe80::1%12]:49900     [2001:db8::9]:5555     ÉTABLI
"""
FRENCH_MANGLED = "  TCP    192.168.1.20:49822     99.81.217.174:5555     �TABLI\n"


def test_english_keeps_established_public_ipv4_on_the_game_port_once() -> None:
    assert parse_netstat(ENGLISH) == ["99.81.217.174", "52.17.4.9"]


def test_french_output_is_understood() -> None:
    assert parse_netstat(FRENCH) == ["99.81.217.174"]


def test_french_state_survives_a_wrong_codepage_decoding() -> None:
    assert parse_netstat(FRENCH_MANGLED) == ["99.81.217.174"]


def test_empty_or_garbage_text_gives_nothing() -> None:
    assert parse_netstat("") == []
    assert parse_netstat("TCP\nfoo bar baz\n  UDP 1.2.3.4:5 6.7.8.9:5555 *:*\n") == []
