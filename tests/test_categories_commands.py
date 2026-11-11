"""Tests of the categories command (show, --enable, --disable), config isolated by conftest."""

import json
import os
from pathlib import Path

from opendofusdata import cli
from opendofusdata.capture_errors import EXIT_FAILED, EXIT_OK


def run(*arguments: str) -> int:
    return cli.run(["categories", *arguments], lambda pipeline, interface: None)


def saved_config() -> dict[str, object]:
    return json.loads(Path(os.environ["OPENDOFUSDATA_CONFIG"]).read_text(encoding="utf-8"))


def test_listing_shows_the_four_categories_and_their_state(capsys) -> None:
    assert run() == EXIT_OK
    output = capsys.readouterr().out
    for label in ("HDV", "Recyclage des ressources", "Brisage", "Expérience des pets"):
        assert label in output
    assert "activée" in output and "bientôt" in output


def test_disable_hdv_is_saved_and_survives_a_listing(capsys) -> None:
    assert run("--disable", "hdv") == EXIT_OK
    assert saved_config()["enabled_categories"] == []
    run()
    assert "désactivée" in capsys.readouterr().out


def test_enable_hdv_again(capsys) -> None:
    run("--disable", "hdv")
    assert run("--enable", "hdv") == EXIT_OK
    assert saved_config()["enabled_categories"] == ["hdv"]


def test_unknown_category_fails_and_lists_the_known_keys(capsys) -> None:
    assert run("--enable", "xyz") == EXIT_FAILED
    error = capsys.readouterr().err
    assert "xyz" in error and "hdv" in error


def test_a_category_without_decoder_cannot_be_enabled(capsys) -> None:
    assert run("--enable", "pets") == EXIT_FAILED
    assert "pas encore disponible" in capsys.readouterr().err


def test_other_config_keys_are_kept(capsys) -> None:
    Path(os.environ["OPENDOFUSDATA_CONFIG"]).write_text('{"server": "Brial"}', encoding="utf-8")
    run("--disable", "hdv")
    assert saved_config()["server"] == "Brial"
