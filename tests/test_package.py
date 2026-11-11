import re
import tomllib
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"
SEMANTIC_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def test_package_is_importable() -> None:
    import opendofusdata  # noqa: F401


def test_product_version_is_a_semantic_version() -> None:
    from opendofusdata import __version__

    assert SEMANTIC_VERSION.match(__version__)


def test_the_version_never_goes_below_the_first_release() -> None:
    from opendofusdata import __version__

    assert tuple(int(part) for part in __version__.split(".")) >= (1, 0, 0)


def test_packaging_reads_the_version_from_the_package() -> None:
    project = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert "version" in project["project"]["dynamic"]
    assert "version" not in project["project"]
    assert project["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "opendofusdata.__version__"}
