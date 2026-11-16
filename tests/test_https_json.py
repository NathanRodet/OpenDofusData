"""The shared HTTPS JSON requester: secure only, bounded, no redirect, nothing secret in errors."""

import http.client
import io
import json
import logging
import urllib.error

import pytest

from opendofusdata.https_json import (
    BAD_RESPONSE, INSECURE, MAX_RESPONSE_BYTES, OPENER, REDIRECT, REQUEST_TIMEOUT_SECONDS, TIMEOUT, UNREACHABLE,
    HttpsFailure, request_json,
)
from opendofusdata.names_fetch import NoRedirectHandler

BASE = "https://sync.exemple.fr"
TOKEN = "jeton-secret-de-test"


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status, self._body = status, body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *details: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self._body if amount < 0 else self._body[:amount]


class FakeOpener:
    def __init__(self, outcome: object) -> None:
        self.outcome, self.calls = outcome, []

    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def http_error(code: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(BASE, code, "message", {}, io.BytesIO(body))


def failure_reason(outcome: object) -> str:
    with pytest.raises(HttpsFailure) as failure:
        request_json(BASE, "GET", "/check", TOKEN, opener=FakeOpener(outcome))
    return failure.value.reason


def test_reads_a_json_object() -> None:
    opener = FakeOpener(FakeResponse(b'{"status": "ok"}'))
    assert request_json(BASE, "GET", "/check", opener=opener) == (200, {"status": "ok"})


def test_request_carries_the_bearer_token_json_headers_method_and_timeout() -> None:
    opener = FakeOpener(FakeResponse(b"{}"))
    request_json(BASE, "POST", "/admin/revoke", TOKEN, {"key_id": "AAAAAAAAAAA"}, opener)
    request, timeout = opener.calls[0]
    assert request.full_url == BASE + "/admin/revoke" and request.get_method() == "POST"
    assert request.get_header("Authorization") == f"Bearer {TOKEN}"
    assert request.get_header("Content-type") == "application/json"
    assert json.loads(request.data) == {"key_id": "AAAAAAAAAAA"}
    assert timeout == REQUEST_TIMEOUT_SECONDS


def test_a_request_without_token_or_body_has_no_authorization_nor_data() -> None:
    opener = FakeOpener(FakeResponse(b"{}"))
    request_json(BASE, "GET", "/check", opener=opener)
    request = opener.calls[0][0]
    assert request.get_header("Authorization") is None and request.data is None


@pytest.mark.parametrize("base", ["http://sync.exemple.fr", "ftp://sync.exemple.fr", "sync.exemple.fr", ""])
def test_a_non_https_address_is_refused_before_any_request(base: str) -> None:
    opener = FakeOpener(FakeResponse(b"{}"))
    with pytest.raises(HttpsFailure) as failure:
        request_json(base, "GET", "/check", TOKEN, opener=opener)
    assert failure.value.reason == INSECURE and opener.calls == []


@pytest.mark.parametrize("code", [301, 302, 307, 308])
def test_redirects_are_refused(code: int) -> None:
    assert failure_reason(http_error(code)) == REDIRECT


def test_the_real_opener_refuses_redirects() -> None:
    assert any(isinstance(handler, NoRedirectHandler) for handler in OPENER.handlers)


def test_error_statuses_are_returned_with_their_json_body() -> None:
    opener = FakeOpener(http_error(401, b'{"detail": "unauthorized"}'))
    assert request_json(BASE, "GET", "/check", TOKEN, opener=opener) == (401, {"detail": "unauthorized"})


def test_an_error_status_with_a_body_that_is_not_json_gives_an_empty_object() -> None:
    assert request_json(BASE, "GET", "/check", opener=FakeOpener(http_error(502, b"<html>"))) == (502, {})


@pytest.mark.parametrize("outcome, reason", [
    (TimeoutError(), TIMEOUT),
    (urllib.error.URLError(TimeoutError()), TIMEOUT),
    (urllib.error.URLError("nom inconnu"), UNREACHABLE),
    (ConnectionResetError(), UNREACHABLE),
    (OSError("réseau coupé"), UNREACHABLE),
])
def test_network_problems_become_a_failure_with_a_reason(outcome: Exception, reason: str) -> None:
    assert failure_reason(outcome) == reason


@pytest.mark.parametrize("body", [b"pas du json", b"[1, 2]", b'"texte"', b"", b"\xff\xfe", b"{" * 5000])
def test_responses_that_are_not_a_json_object_are_bad(body: bytes) -> None:
    assert failure_reason(FakeResponse(body)) == BAD_RESPONSE


def test_an_oversized_response_is_bad() -> None:
    body = b'{"a": "' + b"x" * MAX_RESPONSE_BYTES + b'"}'
    assert failure_reason(FakeResponse(body)) == BAD_RESPONSE


def test_the_token_never_appears_in_errors_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    outcomes = [TimeoutError(TOKEN), urllib.error.URLError(TOKEN), http_error(302), FakeResponse(TOKEN.encode())]
    with caplog.at_level(logging.DEBUG):
        for outcome in outcomes:
            with pytest.raises(HttpsFailure) as failure:
                request_json(BASE, "GET", "/check", TOKEN, opener=FakeOpener(outcome))
            assert TOKEN not in str(failure.value) and TOKEN not in repr(failure.value)
    assert TOKEN not in caplog.text


class BrokenBody:
    """An error body that is cut short by the network."""

    def read(self, amount: int = -1) -> bytes:
        raise http.client.IncompleteRead(b"partial")

    def close(self) -> None:
        return None


def test_a_truncated_error_body_still_gives_the_status() -> None:
    error = urllib.error.HTTPError(BASE, 502, "message", {}, BrokenBody())
    assert request_json(BASE, "GET", "/check", opener=FakeOpener(error)) == (502, {})


def test_request_json_accepts_a_larger_cap_when_asked() -> None:
    body = json.dumps({"filler": "x" * (MAX_RESPONSE_BYTES + 10)}).encode()
    status, answer = request_json(BASE, "GET", "/big", opener=FakeOpener(FakeResponse(body)),
                                  max_response_bytes=MAX_RESPONSE_BYTES * 2)
    assert status == 200 and len(answer["filler"]) == MAX_RESPONSE_BYTES + 10


def test_request_json_default_cap_is_unchanged() -> None:
    body = json.dumps({"filler": "x" * (MAX_RESPONSE_BYTES + 10)}).encode()
    with pytest.raises(HttpsFailure) as failure:
        request_json(BASE, "GET", "/big", opener=FakeOpener(FakeResponse(body)))
    assert failure.value.reason == BAD_RESPONSE
