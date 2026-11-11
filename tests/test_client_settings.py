"""Tests of the persistent client settings helpers."""

from opendofusdata.client_settings import (
    DATABASE_KEY, DEFAULT_DATABASE, choose_database_path, config_with_database,
    config_with_server, database_from_config, server_names,
)
from opendofusdata.server_choice import SERVER_KEY


def test_database_from_config_reads_a_non_empty_string() -> None:
    assert database_from_config({DATABASE_KEY: "C:/data/prices.db"}) == "C:/data/prices.db"


def test_database_from_config_ignores_missing_blank_or_wrong_type() -> None:
    for config in ({}, {DATABASE_KEY: ""}, {DATABASE_KEY: "  "}, {DATABASE_KEY: 3}):
        assert database_from_config(config) is None


def test_config_with_database_keeps_other_keys() -> None:
    config = config_with_database({SERVER_KEY: "Brial"}, "x.db")
    assert config == {SERVER_KEY: "Brial", DATABASE_KEY: "x.db"}


def test_config_with_server_keeps_other_keys() -> None:
    assert config_with_server({DATABASE_KEY: "x.db"}, "Kourial") == {DATABASE_KEY: "x.db", SERVER_KEY: "Kourial"}


def test_option_beats_config_beats_default() -> None:
    config = {DATABASE_KEY: "saved.db"}
    assert choose_database_path("cli.db", config) == "cli.db"
    assert choose_database_path(None, config) == "saved.db"
    assert choose_database_path(None, {}) == DEFAULT_DATABASE


def test_server_names_are_sorted_and_not_empty() -> None:
    names = server_names()
    assert names and names == sorted(names, key=str.casefold)
