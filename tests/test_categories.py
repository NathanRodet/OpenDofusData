"""Tests of the category of each record."""

from opendofusdata.categories import CATEGORY_BREAKING, CATEGORY_HDV, CATEGORY_LABELS, CATEGORY_PETS, category_of
from opendofusdata.records import BrokenItem, LotPrice, MarketStats, PetFeeding, PetState


def test_each_record_type_has_its_category() -> None:
    state = PetState(1, 0, 0, 0)
    assert category_of(LotPrice(307, "Brial", 1, 750, "t")) == CATEGORY_HDV
    assert category_of(MarketStats(307, "Brial", "24h", [], 1, 1, 1, "t", "t", "t")) == CATEGORY_HDV
    assert category_of(PetFeeding("Brial", 1, (), state, state, "t")) == CATEGORY_PETS
    assert category_of(BrokenItem("Brial", 1, 1, 0.5, (), "t")) == CATEGORY_BREAKING


def test_labels_are_the_player_facing_names() -> None:
    assert CATEGORY_LABELS == {CATEGORY_HDV: "HDV", CATEGORY_BREAKING: "Brisage", CATEGORY_PETS: "Familier"}
