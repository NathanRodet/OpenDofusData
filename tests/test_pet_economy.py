"""Tests of the pet experience economics with the real Patte de Gruche and Boue du Boo upgrades."""

from opendofusdata.pet_economy import (
    PET_TOTAL_EXPERIENCE, ResourceExperience, experience_by_resource, experience_per_unit, feeding_gain,
    is_reliable, kamas_per_experience, leveling_cost,
)
from opendofusdata.records import PetFeeding, PetState
from opendofusdata.value_format import format_experience_per_unit, format_kamas

BOUE = 1001
PATTE = 1002


def feeding(resources: tuple[tuple[int, int], ...], before: int | None, after: int | None) -> PetFeeding:
    return PetFeeding("Brial", 7, resources, PetState(35, before, 1000, 0), PetState(35, after, 1000, 0),
                      "2026-11-12T10:00:00Z")


def test_boue_du_boo_nine_units_for_one_experience() -> None:
    stats = experience_by_resource([feeding(((BOUE, 9),), 100, 101)])[BOUE]
    assert experience_per_unit(stats) == 1 / 9
    assert format_experience_per_unit(experience_per_unit(stats)) == "1 XP pour 9"


def test_patte_de_gruche_price_and_leveling_cost() -> None:
    stats = experience_by_resource([feeding(((PATTE, 1),), 10, 12)])[PATTE]
    per_unit = experience_per_unit(stats)
    assert per_unit == 2.0
    ratio = kamas_per_experience(240.0, per_unit)
    assert ratio == 120.0
    assert leveling_cost(ratio) == 120 * PET_TOTAL_EXPERIENCE == 21_550_920
    assert format_kamas(leveling_cost(ratio)) == "21 550 920"


def test_feedings_of_one_resource_add_up() -> None:
    stats = experience_by_resource([feeding(((PATTE, 1),), 0, 2), feeding(((PATTE, 3),), 2, 8)])[PATTE]
    assert stats == ResourceExperience(PATTE, 2, 4, 8)


def test_unusable_upgrades_never_enter_the_ratio() -> None:
    unusable = [feeding(((PATTE, 1), (BOUE, 2)), 0, 5), feeding(((PATTE, 1),), None, 5),
                feeding(((PATTE, 1),), 5, 5), feeding(((PATTE, 1),), 9, 4)]
    assert experience_by_resource(unusable) == {}
    assert feeding_gain(unusable[2]) is None and feeding_gain(unusable[3]) is None


def test_reliability_starts_at_ten_experience() -> None:
    assert not is_reliable(ResourceExperience(PATTE, 3, 3, 9))
    assert is_reliable(ResourceExperience(PATTE, 3, 3, 10))


def test_kamas_per_experience_edge_cases() -> None:
    assert kamas_per_experience(0.0, 2.0) == 0.0
    assert kamas_per_experience(240.0, 0.0) is None
    assert kamas_per_experience(None, 2.0) is None
    assert leveling_cost(None) is None
