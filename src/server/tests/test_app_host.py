"""The application accepts one Host value by default; any other is refused with a generic 400."""

from pathlib import Path

from fastapi.testclient import TestClient

from helpers import KEY_ID, SECRET, authorization
from keyserver.app import create_app
from keyserver.revocations import RevocationStore
from keyserver.settings import INTERNAL_HOST, Settings
from keyserver.signed_keys import make_key


def test_app_accepts_only_the_internal_host(revocations: RevocationStore) -> None:
    app = create_app(Settings(Path(":memory:"), SECRET), revocations)
    key = authorization(make_key(SECRET, KEY_ID))
    assert INTERNAL_HOST == "keyserver.internal"
    accepted = TestClient(app, base_url=f"http://{INTERNAL_HOST}")
    assert accepted.get("/check", headers=key).status_code == 200
    for host in ("autre.exemple.fr", "testserver", "keyserver.internal.evil.fr", "evil.fr"):
        response = TestClient(app, base_url=f"http://{host}").get("/check", headers=key)
        assert response.status_code == 400 and host not in response.text
