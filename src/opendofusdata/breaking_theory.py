"""Expected runes of a breaking from the item stat lines (formula: pdb = 3 x roll x weight x level / 200 + 1)."""

from collections.abc import Iterable, Mapping

from opendofusdata.effects_csv import ItemEffects, Rune

WEIGHT_FACTOR = 3
LEVEL_DIVISOR = 200
FOCUS_OTHER_FACTOR = 0.5  # with a focus, the other stat lines count for half


def base_runes_by_action(runes: Iterable[Rune]) -> dict[int, Rune]:
    """For each stat, its smallest rune (the Ba one); stats with no weight give no rune."""
    base: dict[int, Rune] = {}
    for rune in runes:
        current = base.get(rune.action_id)
        if rune.power_rate > 0 and (current is None or rune.amount < current.amount):
            base[rune.action_id] = rune
    return base


def breaking_weight(roll: int, power_rate: float, level: int) -> float:
    """The breaking weight of one stat line."""
    return WEIGHT_FACTOR * roll * power_rate * level / LEVEL_DIVISOR + 1


def expected_runes(effects: ItemEffects, coefficient: float, base_runes: Mapping[int, Rune],
                   focus_action: int | None = None) -> list[tuple[int, float]]:
    """Expected number of base runes per stat line: weight x coefficient / (stat weight x rune amount).

    With a focus the focused stat counts for 100 % and the other lines for FOCUS_OTHER_FACTOR.
    """
    result = []
    for line in effects.lines:
        rune = base_runes.get(line.action_id)
        if rune is not None:
            factor = 1.0 if focus_action in (None, line.action_id) else FOCUS_OTHER_FACTOR
            weight = breaking_weight(line.maximum, rune.power_rate, effects.level) * factor
            result.append((rune.rune_id, weight * coefficient / (rune.power_rate * rune.amount)))
    return result
