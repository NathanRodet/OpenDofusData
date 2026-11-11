"""Tests for reading servers.csv and the exact name match (pure, temp files only)."""

import logging
from pathlib import Path

from opendofusdata.game_servers import (
    BUNDLED_CLASSIC_SERVERS,
    GameServer,
    available_servers,
    canonical_name,
    load_servers,
)

HEADER = "id,name_fr,game_type_id,game_type_fr,community_id\n"


def test_load_reads_every_column(tmp_path: Path) -> None:
    path = tmp_path / "servers.csv"
    path.write_text(HEADER + "293,Tylezia,0,Classique,2\n901,[!] X,3,,\n", encoding="utf-8")
    assert load_servers(path) == [GameServer(293, "Tylezia", 0, "Classique", 2),
                                  GameServer(901, "[!] X", 3, "", None)]


def test_missing_file_gives_an_empty_list(tmp_path: Path) -> None:
    assert load_servers(tmp_path / "absent.csv") == []


def test_malformed_rows_are_skipped_with_a_warning(tmp_path: Path, caplog) -> None:
    path = tmp_path / "servers.csv"
    path.write_text(HEADER + "x,Bad,0,C,1\n5,,0,C,1\n6,Short\n7,Ok,0,C,1\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert [server.server_id for server in load_servers(path)] == [7]
    assert len(caplog.records) == 3


def test_duplicate_id_keeps_the_last_row(tmp_path: Path) -> None:
    path = tmp_path / "servers.csv"
    path.write_text(HEADER + "5,Old,0,C,1\n6,Six,0,C,1\n5,New,0,C,1\n", encoding="utf-8")
    assert load_servers(path) == [GameServer(5, "New", 0, "C", 1),
                                  GameServer(6, "Six", 0, "C", 1)]


def test_out_of_range_numbers_are_skipped_with_a_warning(tmp_path: Path, caplog) -> None:
    huge = 2 ** 63
    rows = [f"{huge},Big,0,C,1", "-3,Neg,0,C,1", f"8,Type,{huge},C,1",
            f"9,Comm,0,C,{huge}", f"{huge - 1},Max,0,C,1"]
    path = tmp_path / "servers.csv"
    path.write_text(HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert [server.server_id for server in load_servers(path)] == [huge - 1]
    assert len(caplog.records) == 4


def test_canonical_name_is_exact_and_case_insensitive() -> None:
    servers = [GameServer(295, "Draconiros", 0, "Classique", 0),
               GameServer(294, "Hell Mina", 0, "Classique", 0)]
    assert canonical_name(servers, "draconiros") == "Draconiros"
    assert canonical_name(servers, "HELL MINA") == "Hell Mina"
    assert canonical_name(servers, "Dracon") is None
    assert canonical_name(servers, "Dracóniros") is None
    assert canonical_name([], "x") is None


def test_bundled_list_has_the_thirteen_classic_servers() -> None:
    assert len(BUNDLED_CLASSIC_SERVERS) == 13
    assert all(server.game_type_id == 0 and server.game_type == "Classique"
               for server in BUNDLED_CLASSIC_SERVERS)
    assert GameServer(355, "Kourial", 0, "Classique", 12) in BUNDLED_CLASSIC_SERVERS
    assert GameServer(290, "Tal Kasha", 0, "Classique", 2) in BUNDLED_CLASSIC_SERVERS
    assert GameServer(291, "Imagiro", 0, "Classique", 0) in BUNDLED_CLASSIC_SERVERS
    assert GameServer(800, "Shukrute", 0, "Classique", 8) in BUNDLED_CLASSIC_SERVERS


def test_available_servers_falls_back_to_the_bundled_list(tmp_path: Path) -> None:
    assert available_servers(tmp_path / "absent.csv") == list(BUNDLED_CLASSIC_SERVERS)
    empty = tmp_path / "servers.csv"
    empty.write_text(HEADER + "x,Bad,0,C,1" + chr(10), encoding="utf-8")
    assert available_servers(empty) == list(BUNDLED_CLASSIC_SERVERS)


def test_available_servers_prefers_the_file_rows(tmp_path: Path) -> None:
    path = tmp_path / "servers.csv"
    path.write_text(HEADER + "9,Zed,77,,1" + chr(10), encoding="utf-8")
    assert available_servers(path) == [GameServer(9, "Zed", 77, "", 1)]
