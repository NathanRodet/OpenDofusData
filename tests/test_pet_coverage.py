"""Pet coverage: coefficients known out of the possible resources, missing ones by category."""

from opendofusdata.pet_coverage import build_coverage

ITEMS = [(1, "Os de Bouftou", "Os"), (2, "Os de Tofu", "Os"), (3, "Os de Gobball", "Os"),
         (4, "Poil de Bouftou", "Poil"), (5, "Épée", "Épée"), (6, "Sans type", "")]


def test_possible_resources_are_the_items_of_the_categories_with_a_known_coefficient() -> None:
    coverage = build_coverage(ITEMS, {1, 4})
    assert (coverage.covered, coverage.total) == (2, 4)
    assert [item.name for item in coverage.missing] == ["Os de Gobball", "Os de Tofu"]
    assert coverage.categories() == ["Os"]


def test_nothing_is_possible_without_any_coefficient() -> None:
    coverage = build_coverage(ITEMS, set())
    assert (coverage.covered, coverage.total, coverage.missing) == (0, 0, ())


def test_an_untyped_covered_item_does_not_open_every_untyped_item() -> None:
    assert build_coverage(ITEMS, {6}).total == 0
