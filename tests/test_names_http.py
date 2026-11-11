"""Tests for the HTTP layer of the names download (no real network)."""

import http.client
import http.server
import io
import threading
import urllib.error
from collections.abc import Iterator

import pytest

from opendofusdata import names_fetch
from opendofusdata.names_fetch import NamesFetchError, TransientFetchError, http_get_json

LOCAL_HOST = "127.0.0.1"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def patch_urlopen(monkeypatch, behaviour) -> list:
    requests: list = []

    def fake_open(request, timeout):
        requests.append((request, timeout))
        return behaviour()

    monkeypatch.setattr(names_fetch.OPENER, "open", fake_open)
    return requests


def test_http_get_json_sends_user_agent_and_parses(monkeypatch) -> None:
    requests = patch_urlopen(monkeypatch, lambda: FakeResponse(b'{"a": 1}'))
    assert http_get_json("https://api.dofusdb.fr/items") == {"a": 1}
    request, timeout = requests[0]
    assert request.get_header("User-agent") == names_fetch.USER_AGENT and timeout > 0


@pytest.mark.parametrize("code, expected", [(429, TransientFetchError), (503, TransientFetchError),
                                            (404, NamesFetchError)])
def test_http_status_classification(monkeypatch, code, expected) -> None:
    def behaviour():
        raise urllib.error.HTTPError("u", code, "m", None, None)

    patch_urlopen(monkeypatch, behaviour)
    with pytest.raises(expected):
        http_get_json("https://api.dofusdb.fr/items")


def test_network_error_is_transient_and_bad_json_is_not(monkeypatch) -> None:
    def unreachable():
        raise urllib.error.URLError("down")

    patch_urlopen(monkeypatch, unreachable)
    with pytest.raises(TransientFetchError):
        http_get_json("https://api.dofusdb.fr/items")
    patch_urlopen(monkeypatch, lambda: FakeResponse(b"<html>"))
    with pytest.raises(NamesFetchError, match="JSON"):
        http_get_json("https://api.dofusdb.fr/items")


def test_http_exceptions_are_transient(monkeypatch) -> None:
    def truncated():
        raise http.client.IncompleteRead(b"par")

    patch_urlopen(monkeypatch, truncated)
    with pytest.raises(TransientFetchError):
        http_get_json("https://api.dofusdb.fr/items")


class RedirectingServer:
    """Throwaway local server: /start answers 302 to /target, every path is recorded."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner.paths.append(self.path)
                self.send_response(302 if self.path == "/start" else 200)
                self.send_header("Location", f"http://{LOCAL_HOST}:{owner.port}/target")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args) -> None:
                return None

        self._server = http.server.HTTPServer((LOCAL_HOST, 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "RedirectingServer":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()


@pytest.fixture
def redirecting_server() -> Iterator[RedirectingServer]:
    with RedirectingServer() as server:
        yield server


def test_redirect_is_refused_and_its_target_never_requested(redirecting_server) -> None:
    with pytest.raises(NamesFetchError, match="redirection"):
        http_get_json(f"http://{LOCAL_HOST}:{redirecting_server.port}/start")
    assert redirecting_server.paths == ["/start"]


def test_real_opener_still_reads_a_plain_answer(redirecting_server) -> None:
    assert http_get_json(f"http://{LOCAL_HOST}:{redirecting_server.port}/plain") == {}
