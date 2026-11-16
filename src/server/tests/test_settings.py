"""Server settings refuse to start without a real secret; `new-secret` prints one."""

import io
from pathlib import Path

import pytest

from keyserver.cli import main
from keyserver.settings import DEFAULT_DATABASE_PATH, Settings, SettingsError, load_settings
from keyserver.signed_keys import MIN_SECRET_LENGTH, signature_is_valid, make_key

SECRET = "A" * 43


@pytest.mark.parametrize("environ", [
    {},
    {"KEY_SECRET": ""},
    {"KEY_SECRET": "   "},
    {"KEY_SECRET": "A" * (MIN_SECRET_LENGTH - 1)},
])
def test_secret_missing_blank_or_too_short_raises(environ: dict[str, str]) -> None:
    with pytest.raises(SettingsError):
        load_settings(environ)


def test_valid_environment_gives_settings_with_the_default_database_path() -> None:
    settings = load_settings({"KEY_SECRET": SECRET})
    assert settings == Settings(db_path=DEFAULT_DATABASE_PATH, key_secret=SECRET)
    assert DEFAULT_DATABASE_PATH.name == "keys.db"
    assert DEFAULT_DATABASE_PATH.parent.name == "server"


def test_allowed_hosts_default_to_the_internal_host_and_can_be_overridden() -> None:
    assert load_settings({"KEY_SECRET": SECRET}).allowed_hosts == ("keyserver.internal",)
    environ = {"KEY_SECRET": SECRET, "KEYSERVER_ALLOWED_HOSTS": "127.0.0.1, localhost ,"}
    assert load_settings(environ).allowed_hosts == ("127.0.0.1", "localhost")


def test_database_path_can_be_overridden() -> None:
    settings = load_settings({"KEY_SECRET": SECRET, "KEYSERVER_DB": "/data/keys.db"})
    assert settings.db_path == Path("/data/keys.db")


def test_the_error_never_contains_the_secret() -> None:
    with pytest.raises(SettingsError) as error:
        load_settings({"KEY_SECRET": "trop-court"})
    assert "trop-court" not in str(error.value)


def test_new_secret_command_prints_both_lines_with_the_same_valid_secret_and_returns_0() -> None:
    out = io.StringIO()
    assert main(["new-secret"], out) == 0
    lines = out.getvalue().splitlines()
    assert [line.split("=", 1)[0] for line in lines] == ["KEY_SECRET", "ADMIN_SECRET"]
    secrets_printed = {line.split("=", 1)[1] for line in lines}
    assert len(secrets_printed) == 1
    secret = secrets_printed.pop()
    assert len(secret) >= MIN_SECRET_LENGTH
    assert signature_is_valid(secret, make_key(secret, "AAAAAAAAAAA"))


def test_unknown_subcommand_is_refused() -> None:
    with pytest.raises(SystemExit) as refusal:
        main(["create"], io.StringIO())
    assert refusal.value.code == 2
