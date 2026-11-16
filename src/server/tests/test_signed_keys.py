"""Signed API keys: format, signature, tampering and the shared test vector."""

import pytest

from keyserver.signed_keys import (
    KEY_PATTERN, MIN_SECRET_LENGTH, admin_token, generate_secret, make_key, new_key_id, parse_key,
    signature_is_valid,
)

SECRET = "A" * 43
KEY_ID = "AAAAAAAAAAA"
# The client suite (tests/test_admin_keys.py) pins the very same values.
VECTOR_KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"
VECTOR_ADMIN_TOKEN = "ryCt2NoWglWabZcwLAcIZJImdIuVA1hNvltX2Hf0lCM"


def test_generated_secret_is_long_enough_and_distinct() -> None:
    first, second = generate_secret(), generate_secret()
    assert len(first) >= MIN_SECRET_LENGTH
    assert first != second


def test_made_key_matches_the_pattern_and_verifies() -> None:
    key = make_key(SECRET, new_key_id())
    assert KEY_PATTERN.match(key)
    assert signature_is_valid(SECRET, key)


def test_new_key_ids_are_distinct_and_well_formed() -> None:
    ids = {new_key_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(len(key_id) == 11 for key_id in ids)


def flip(text: str, index: int) -> str:
    replacement = "B" if text[index] != "B" else "C"
    return text[:index] + replacement + text[index + 1:]


@pytest.mark.parametrize("mutate", [
    lambda key: flip(key, 6),                       # one character of the identifier
    lambda key: flip(key, len(key) - 1),            # one character of the signature
    lambda key: key[:-1],                           # truncated
    lambda key: "odk2" + key[4:],                   # another prefix
    lambda key: "",                                 # empty
    lambda key: key + "A" * 10_000,                 # huge
    lambda key: key + "\n",                         # trailing line feed
    lambda key: " " + key,                          # leading space
])
def test_tampered_truncated_wrongly_prefixed_or_oversized_keys_fail(mutate) -> None:
    key = make_key(SECRET, KEY_ID)
    assert not signature_is_valid(SECRET, mutate(key))


def test_a_key_signed_by_another_secret_fails() -> None:
    assert not signature_is_valid(SECRET, make_key("B" * 43, KEY_ID))


def test_parse_key_is_strict() -> None:
    assert parse_key(VECTOR_KEY) == KEY_ID
    for bad in ("", "odk1.x.y", VECTOR_KEY + "\n", VECTOR_KEY[:-1], "Bearer " + VECTOR_KEY, VECTOR_KEY.replace("odk1", "odk9")):
        assert parse_key(bad) is None


def test_admin_token_differs_from_the_secret_and_from_any_key() -> None:
    token = admin_token(SECRET)
    assert token != SECRET
    assert token not in make_key(SECRET, KEY_ID)
    assert not signature_is_valid(SECRET, token)


def test_known_vector() -> None:
    assert make_key(SECRET, KEY_ID) == VECTOR_KEY
    assert admin_token(SECRET) == VECTOR_ADMIN_TOKEN
