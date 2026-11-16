"""Admin side of the keys: generation on the administrator's PC, identical to the server's maths."""

from opendofusdata.admin_keys import admin_token, make_key, new_key_id
from opendofusdata.sync_key import key_format_ok

SECRET = "A" * 43
KEY_ID = "AAAAAAAAAAA"
# The server suite (src/server/tests/test_signed_keys.py) pins the very same values.
VECTOR_KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"
VECTOR_ADMIN_TOKEN = "ryCt2NoWglWabZcwLAcIZJImdIuVA1hNvltX2Hf0lCM"


def test_the_vector_matches_the_server() -> None:
    assert make_key(SECRET, KEY_ID) == VECTOR_KEY
    assert admin_token(SECRET) == VECTOR_ADMIN_TOKEN


def test_a_made_key_has_the_expected_format() -> None:
    assert key_format_ok(make_key(SECRET, new_key_id()))


def test_new_key_ids_are_distinct_and_eleven_characters_long() -> None:
    ids = {new_key_id() for _ in range(50)}
    assert len(ids) == 50 and all(len(key_id) == 11 for key_id in ids)


def test_the_admin_token_is_not_the_secret_nor_a_key() -> None:
    token = admin_token(SECRET)
    assert token != SECRET and not key_format_ok(token)
