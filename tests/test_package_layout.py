"""The key server lives in src/server but is never shipped with, nor imported by, the client."""

import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_client_package_excludes_the_server() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    find = config["tool"]["setuptools"]["packages"]["find"]
    assert find["include"] == ["opendofusdata*"]


def test_server_does_not_import_the_client() -> None:
    offenders = [str(path) for path in (ROOT / "src" / "server").rglob("*.py")
                 if "opendofusdata" in path.read_text(encoding="utf-8")]
    assert not offenders, offenders
