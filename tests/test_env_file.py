"""The client .env: admin secret and server URL, read tolerantly."""

import pathlib

import pytest

from opendofusdata.env_file import admin_secret, env_file_path, read_env_file, server_url_override

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALID_SECRET = "A" * 43


def write_env(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    path = tmp_path / ".env"
    path.write_text(content, encoding="utf-8")
    return path


def test_reads_plain_and_quoted_values(tmp_path: pathlib.Path) -> None:
    path = write_env(tmp_path, "A=1\nB=\"deux\"\nC='trois'\n")
    assert read_env_file(path) == {"A": "1", "B": "deux", "C": "trois"}


def test_ignores_comments_blank_and_malformed_lines(tmp_path: pathlib.Path) -> None:
    path = write_env(tmp_path, "# note\n\nsansegal\nA=1\n")
    assert read_env_file(path) == {"A": "1"}


def test_missing_file_gives_empty_dict(tmp_path: pathlib.Path) -> None:
    assert read_env_file(tmp_path / "absent.env") == {}


def test_admin_secret_is_none_when_absent_blank_or_too_short_and_returns_a_valid_one(tmp_path: pathlib.Path) -> None:
    assert admin_secret(tmp_path / "absent.env") is None
    assert admin_secret(write_env(tmp_path, "OTHER=1\n")) is None
    assert admin_secret(write_env(tmp_path, "ADMIN_SECRET=\n")) is None
    assert admin_secret(write_env(tmp_path, "ADMIN_SECRET=court\n")) is None
    assert admin_secret(write_env(tmp_path, f"ADMIN_SECRET={VALID_SECRET}\n")) == VALID_SECRET
    assert admin_secret(write_env(tmp_path, f'ADMIN_SECRET="{VALID_SECRET}"\n')) == VALID_SECRET


def test_server_url_accepts_https_and_strips_the_trailing_slash(tmp_path: pathlib.Path) -> None:
    assert server_url_override(write_env(tmp_path, "SERVER_URL=https://exemple.fr/\n")) == "https://exemple.fr"
    assert server_url_override(write_env(tmp_path, "SERVER_URL=https://exemple.fr:8443\n")) == "https://exemple.fr:8443"


@pytest.mark.parametrize("value", [
    "http://exemple.fr", "https://exemple.fr/chemin", "https://exemple.fr?x=1", "https://exemple.fr#frag",
    "https://user:mdp@exemple.fr", "ftp://exemple.fr", "exemple.fr", "", "https://", "https://exemple.fr:abc",
])
def test_server_url_rejects_http_paths_queries_credentials_and_garbage(tmp_path: pathlib.Path, value: str) -> None:
    assert server_url_override(write_env(tmp_path, f"SERVER_URL={value}\n")) is None


@pytest.mark.parametrize("value", [
    "https://exemple.fr\\@autre.fr", "https://exemple.fr\\", "https://exem\tple.fr",
    "https://exemple.fr@autre.fr", "https://exemple.fr:0", "https://exemple.fr:99999",
    "https://exémple.fr", "https://[::1]", "https://exemple_fr", "https://-exemple.fr", "https://exemple..fr",
])
def test_server_url_rejects_characters_that_a_url_parser_and_a_client_could_read_differently(
        tmp_path: pathlib.Path, value: str) -> None:
    assert server_url_override(write_env(tmp_path, f"SERVER_URL={value}\n")) is None


def test_server_url_returns_the_canonical_origin_rebuilt_from_its_parts(tmp_path: pathlib.Path) -> None:
    assert server_url_override(write_env(tmp_path, "SERVER_URL=HTTPS://Exemple.FR:8443/\n")) == "https://exemple.fr:8443"
    assert server_url_override(write_env(tmp_path, "SERVER_URL=https://sync.exemple.fr\n")) == "https://sync.exemple.fr"


def test_server_url_is_none_when_absent(tmp_path: pathlib.Path) -> None:
    assert server_url_override(tmp_path / "absent.env") is None


def test_gitignore_excludes_env_but_not_the_example() -> None:
    lines = [line.strip() for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()]
    assert ".env" in lines
    assert "admin_keys.json" in lines
    assert not any(line in (".env*", "*.env", "*.example") for line in lines)
    assert (ROOT / ".env.example").is_file()


def test_env_file_path_sits_next_to_the_config_file() -> None:
    assert env_file_path(pathlib.Path("dossier/config.json")) == pathlib.Path("dossier/.env")


def test_a_utf8_byte_order_mark_does_not_hide_the_first_variable(tmp_path: pathlib.Path) -> None:
    path = tmp_path / ".env"
    path.write_bytes(b"\xef\xbb\xbf" + f"ADMIN_SECRET={VALID_SECRET}\r\nSERVER_URL=https://sync.exemple.fr\r\n".encode())
    assert admin_secret(path) == VALID_SECRET
    assert server_url_override(path) == "https://sync.exemple.fr"
