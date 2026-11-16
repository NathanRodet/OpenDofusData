"""Revoking a key from the administrator's PC: the admin token travels, the secret never does."""

import logging

import pytest

from opendofusdata import admin_client
from opendofusdata.admin_client import RevokeResult, revoke_key
from opendofusdata.admin_keys import admin_token
from opendofusdata.https_json import HttpsFailure

SECRET = "A" * 43
BASE = "https://sync.exemple.fr"
KEY_ID = "AAAAAAAAAAA"


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


def test_a_revocation_posts_the_key_id_with_the_admin_token_and_never_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = answering(200, {"revoked": True})
    monkeypatch.setattr(admin_client, "request_json", fake)
    assert revoke_key(BASE, SECRET, KEY_ID) == RevokeResult(True, "Clé révoquée")
    base, method, path, token, body = fake.calls[0]
    assert (base, method, path, body) == (BASE, "POST", "/admin/revoke", {"key_id": KEY_ID})
    assert token == admin_token(SECRET) and token != SECRET and SECRET not in str(fake.calls)


@pytest.mark.parametrize("status, message", [
    (401, "Secret d'administration refusé par le serveur"), (422, "Réponse inattendue du serveur"),
    (500, "Réponse inattendue du serveur"), (404, "Réponse inattendue du serveur"),
])
def test_error_statuses_give_clear_messages(monkeypatch: pytest.MonkeyPatch, status: int, message: str) -> None:
    monkeypatch.setattr(admin_client, "request_json", answering(status, {"detail": "x"}))
    assert revoke_key(BASE, SECRET, KEY_ID) == RevokeResult(False, message)


def test_a_200_without_the_confirmation_is_not_a_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_client, "request_json", answering(200, {}))
    assert not revoke_key(BASE, SECRET, KEY_ID).ok


@pytest.mark.parametrize("reason, message", [
    ("unreachable", "Serveur injoignable"), ("timeout", "Serveur injoignable"),
    ("redirect", "Réponse inattendue du serveur"), ("bad_response", "Réponse inattendue du serveur"),
    ("insecure", "Adresse du serveur non sécurisée (https attendu)"),
])
def test_network_failures_give_clear_messages(monkeypatch: pytest.MonkeyPatch, reason: str, message: str) -> None:
    monkeypatch.setattr(admin_client, "request_json", failing(reason))
    assert revoke_key(BASE, SECRET, KEY_ID) == RevokeResult(False, message)


def test_neither_the_secret_nor_the_token_is_in_messages_or_logs(monkeypatch: pytest.MonkeyPatch,
                                                               caplog: pytest.LogCaptureFixture) -> None:
    token = admin_token(SECRET)
    with caplog.at_level(logging.DEBUG):
        for fake in (answering(200, {"revoked": True}), answering(401), failing("timeout")):
            monkeypatch.setattr(admin_client, "request_json", fake)
            result = revoke_key(BASE, SECRET, KEY_ID)
            assert SECRET not in result.message and token not in result.message
    assert SECRET not in caplog.text and token not in caplog.text
