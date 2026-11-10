"""Tests for reading servers.csv and the exact name match (pure, temp files only)."""

import logging
from pathlib import Path

from dofus_prices.game_servers import GameServer, canonical_name, load_servers

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


def test_canonical_name_is_exact_and_case_insensitive() -> None:
    servers = [GameServer(295, "Draconiros", 0, "Classique", 0),
               GameServer(294, "Hell Mina", 0, "Classique", 0)]
    assert canonical_name(servers, "draconiros") == "Draconiros"
    assert canonical_name(servers, "HELL MINA") == "Hell Mina"
    assert canonical_name(servers, "Dracon") is None
    assert canonical_name(servers, "Dracóniros") is None
    assert canonical_name([], "x") is None
