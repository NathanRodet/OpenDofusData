"""Fixtures shared by the server tests: in-memory stores and a client on the full application."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helpers import SECRET
from keyserver.app import create_app
from keyserver.readings_store import ReadingStore, open_readings
from keyserver.revocations import RevocationStore, open_revocations
from keyserver.settings import Settings


@pytest.fixture
def revocations() -> Iterator[RevocationStore]:
    store = open_revocations(":memory:")
    yield store
    store.close()


@pytest.fixture
def readings() -> Iterator[ReadingStore]:
    store = open_readings(":memory:")
    yield store
    store.close()


@pytest.fixture
def client(revocations: RevocationStore, readings: ReadingStore) -> TestClient:
    return TestClient(create_app(Settings(Path(":memory:"), SECRET, ("testserver",)), revocations, readings))
