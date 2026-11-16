"""The connection test of the player: one GET /check with the key, and a clear message either way."""

import logging
from pathlib import Path

import pytest

from opendofusdata import sync_client
from opendofusdata.https_json import HttpsFailure
from opendofusdata.sync_client import ConnectionResult, check_connection, resolve_server_url

BASE = "https://sync.exemple.fr"
KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"


def answering(status: int, reply: dict | None = None):
    calls: list[tuple] = []

    def fake(base_url, method, path, token=None, body=None, opener=None):
        calls.append((base_url, method, path, token, body))
        return status, reply or {}

    fake.calls = calls
    return fake


def failing(reason: str):
    def fake(*arguments, **keywords):
        raise HttpsFailure(reason)

    return fake


def test_a_valid_key_gives_a_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = answering(200, {"status": "ok"})
    monkeypatch.setattr(sync_client, "request_json", fake)
    result = check_connection(BASE, KEY)
    assert result == ConnectionResult(True, "Connexion réussie")
    assert fake.calls == [(BASE, "GET", "/check", KEY, None)]


@pytest.mark.parametrize("status, message", [
    (401, "Clé refusée ou révoquée"), (403, "Réponse inattendue du serveur"), (404, "Réponse inattendue du serveur"),
    (429, "Réponse inattendue du serveur"), (500, "Réponse inattendue du serveur"), (200, "Réponse inattendue du serveur"),
])
def test_other_statuses_give_a_failure_with_a_clear_message(monkeypatch: pytest.MonkeyPatch, status: int,
                                                            message: str) -> None:
    body = {} if status == 200 else {"detail": "x"}  # a 200 without {"status": "ok"} is not a success
    monkeypatch.setattr(sync_client, "request_json", answering(status, body))
    assert check_connection(BASE, KEY) == ConnectionResult(False, message)


@pytest.mark.parametrize("reason, message", [
    ("unreachable", "Serveur injoignable"), ("timeout", "Serveur injoignable"),
    ("redirect", "Réponse inattendue du serveur"), ("bad_response", "Réponse inattendue du serveur"),
    ("insecure", "Adresse du serveur non sécurisée (https attendu)"),
])
def test_network_failures_give_a_clear_message(monkeypatch: pytest.MonkeyPatch, reason: str, message: str) -> None:
    monkeypatch.setattr(sync_client, "request_json", failing(reason))
    assert check_connection(BASE, KEY) == ConnectionResult(False, message)


def test_the_key_is_never_in_the_message_nor_the_logs(monkeypatch: pytest.MonkeyPatch,
                                                      caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        for fake in (answering(200, {"status": "ok"}), answering(401), failing("timeout")):
            monkeypatch.setattr(sync_client, "request_json", fake)
            assert KEY not in check_connection(BASE, KEY).message
    assert KEY not in caplog.text


def test_the_address_comes_from_the_env_override_then_the_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    monkeypatch.setattr(sync_client, "DEFAULT_SERVER_URL", "")
    assert resolve_server_url(env) is None
    env.write_text("SERVER_URL=https://perso.exemple.fr\n", encoding="utf-8")
    assert resolve_server_url(env) == "https://perso.exemple.fr"
    env.write_text("SERVER_URL=http://pas-https.fr\n", encoding="utf-8")
    assert resolve_server_url(env) is None
    monkeypatch.setattr(sync_client, "DEFAULT_SERVER_URL", "https://defaut.exemple.fr")
    assert resolve_server_url(env) == "https://defaut.exemple.fr"
    assert resolve_server_url(tmp_path / "absent.env") == "https://defaut.exemple.fr"
