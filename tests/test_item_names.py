"""Tests for the pure item-name index."""

import logging
from pathlib import Path

import pytest

from dofus_prices.item_names import ITEMS_CSV_HEADER, ItemNames

SYNTHETIC_ROW_COUNT = 3000


def write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join([",".join(ITEMS_CSV_HEADER), *rows]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def names(tmp_path: Path) -> ItemNames:
    path = write_csv(tmp_path / "items.csv", [
        "307,Ailes de Moskito,1,Aile",
        "376,Aile du Tofu Maléfique,20,Aile",
        "400,Aile,5,Aile",
        '500,"Aile, grande",5,Aile',
        "600,Épée de Boisaille,3,",
    ])
    return ItemNames.load(path)


def test_missing_file_gives_an_empty_index(tmp_path: Path) -> None:
    index = ItemNames.load(tmp_path / "absent.csv")
    assert len(index) == 0
    assert index.name_of(307) is None


def test_name_of(names: ItemNames) -> None:
    assert names.name_of(307) == "Ailes de Moskito"
    assert names.name_of(1) is None


def test_empty_level_and_type_are_accepted(tmp_path: Path) -> None:
    index = ItemNames.load(write_csv(tmp_path / "items.csv", ["7,Truc,,", '8,"Machin, bis",4,T']))
    assert (index.name_of(7), index.name_of(8)) == ("Truc", "Machin, bis")


def test_malformed_rows_are_skipped_with_a_warning(tmp_path: Path, caplog) -> None:
    path = write_csv(tmp_path / "items.csv", ["abc,Mauvais,1,T", "8,Seul", "9,Bon,2,T", "10,Niveau,x,T"])
    with caplog.at_level(logging.WARNING):
        index = ItemNames.load(path)
    assert len(index) == 1 and index.name_of(9) == "Bon"
    assert caplog.text.count("ignorée") == 3


def test_large_index_is_correct(tmp_path: Path) -> None:
    rows = [f"{number},Objet numéro {number},{number % 200},Type" for number in range(SYNTHETIC_ROW_COUNT)]
    index = ItemNames.load(write_csv(tmp_path / "items.csv", rows))
    assert len(index) == SYNTHETIC_ROW_COUNT
    assert index.name_of(2999) == "Objet numéro 2999"
    assert index.name_of(0) == "Objet numéro 0" and index.name_of(SYNTHETIC_ROW_COUNT) is None


def test_unreadable_file_gives_an_empty_index_with_a_warning(tmp_path: Path, caplog) -> None:
    path = tmp_path / "items.csv"
    path.write_bytes(b"id,name_fr,level,type_fr\n1,\xff\xfe,1,T\n")
    with caplog.at_level(logging.WARNING):
        index = ItemNames.load(path)
    assert len(index) == 0 and "illisible" in caplog.text
