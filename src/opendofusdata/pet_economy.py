"""Pet experience per resource and the kamas it costs: pure logic."""

from collections.abc import Iterable
from dataclasses import dataclass

from opendofusdata.records import PetFeeding

PET_TOTAL_EXPERIENCE = 179_591
MIN_RELIABLE_EXPERIENCE = 10


@dataclass(frozen=True)
class ResourceExperience:
    """Usable single-resource upgrades of one resource, added up."""

    item_id: int
    feedings: int
    units: int
    experience: int


def feeding_gain(feeding: PetFeeding) -> int | None:
    """The experience an upgrade gave; None when it is unknown or not positive."""
    before, after = feeding.before.experience, feeding.after.experience
    if before is None or after is None or after - before <= 0:
        return None
    return after - before


def _usable_resource(feeding: PetFeeding) -> tuple[int, int, int] | None:
    gain = feeding_gain(feeding)
    if gain is None or len(feeding.resources) != 1:
        return None
    item_id, units = feeding.resources[0]
    return (item_id, units, gain) if units > 0 else None


def experience_by_resource(feedings: Iterable[PetFeeding]) -> dict[int, ResourceExperience]:
    """Experience per resource, from the upgrades that fed exactly one resource with a known gain."""
    totals: dict[int, ResourceExperience] = {}
    for feeding in feedings:
        usable = _usable_resource(feeding)
        if usable is None:
            continue
        item_id, units, gain = usable
        known = totals.get(item_id, ResourceExperience(item_id, 0, 0, 0))
        totals[item_id] = ResourceExperience(item_id, known.feedings + 1, known.units + units,
                                             known.experience + gain)
    return totals


def experience_per_unit(stats: ResourceExperience) -> float | None:
    """Experience given by one unit of the resource."""
    return stats.experience / stats.units if stats.units > 0 else None


def kamas_per_experience(unit_price: float | None, per_unit: float | None) -> float | None:
    """Kamas spent for one experience point; None when the price or the experience is unknown."""
    if unit_price is None or per_unit is None or per_unit <= 0:
        return None
    return unit_price / per_unit


def leveling_cost(kamas_per_xp: float | None) -> float | None:
    """Kamas needed to take a pet from the start to the end with this resource."""
    return None if kamas_per_xp is None else kamas_per_xp * PET_TOTAL_EXPERIENCE


def is_reliable(stats: ResourceExperience) -> bool:
    """True once enough experience was observed to trust the ratio."""
    return stats.experience >= MIN_RELIABLE_EXPERIENCE
