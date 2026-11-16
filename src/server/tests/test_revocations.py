"""The revocation list: persistent, idempotent, and answering only for ids it was told about."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from keyserver.revocations import RevocationStore, open_revocations

KEY_ID = "AAAAAAAAAAA"
OTHER_ID = "BBBBBBBBBBB"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[RevocationStore]:
    revocations = open_revocations(tmp_path / "keys.db")
    yield revocations
    revocations.close()


def test_unknown_id_is_not_revoked(store: RevocationStore) -> None:
    assert not store.is_revoked(KEY_ID)


def test_revoke_marks_only_that_id(store: RevocationStore) -> None:
    store.revoke(KEY_ID)
    assert store.is_revoked(KEY_ID)
    assert not store.is_revoked(OTHER_ID)


def test_revoke_is_idempotent_and_survives_reopening_the_file(store: RevocationStore, tmp_path: Path) -> None:
    store.revoke(KEY_ID)
    store.revoke(KEY_ID)
    reopened = open_revocations(tmp_path / "keys.db")
    try:
        assert reopened.is_revoked(KEY_ID)
    finally:
        reopened.close()
