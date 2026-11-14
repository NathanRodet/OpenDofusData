"""The two ways to break an object, classic and focus, valued with the runes the formula expects."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from opendofusdata.breaking_theory import expected_runes
from opendofusdata.effects_csv import ItemEffects, Rune


@dataclass(frozen=True)
class RuneLine:
    """One rune type: expected count, mean count really obtained (None when unknown) and unit price."""

    rune_id: int
    expected: float
    real: float | None
    unit_price: float | None

    @property
    def value(self) -> float | None:
        """Expected value of this rune type; None when its price is unknown."""
        return None if self.unit_price is None else self.expected * self.unit_price


@dataclass(frozen=True)
class Scenario:
    """A breaking mode: its focus (None for classic), the rune lines, their value and the plus-value."""

    focus_rune: int | None
    lines: tuple[RuneLine, ...]
    value: float
    plus_value: float | None
    partial: bool


def build_scenario(effects: ItemEffects, coefficient: float, base_runes: Mapping[int, Rune],
                   price_of: Callable[[int], float | None], hdv_price: float | None,
                   real_runes: Mapping[int, float], focus_action: int | None = None) -> Scenario:
    """Value one mode; runes really obtained but not modelled (Pa, Ra) are listed with an expected count of 0."""
    expected = dict(expected_runes(effects, coefficient, base_runes, focus_action))
    lines = [RuneLine(rune, count, real_runes.get(rune), price_of(rune)) for rune, count in expected.items()]
    if focus_action is None:
        lines += [RuneLine(rune, 0.0, count, price_of(rune)) for rune, count in real_runes.items()
                  if rune not in expected]
    value = sum(line.value or 0.0 for line in lines)
    focus_rune = base_runes[focus_action].rune_id if focus_action is not None else None
    return Scenario(focus_rune, tuple(lines), value, None if hdv_price is None else value - hdv_price,
                    any(line.value is None for line in lines))


def best_focus(effects: ItemEffects, coefficient: float, base_runes: Mapping[int, Rune],
               price_of: Callable[[int], float | None], hdv_price: float | None) -> Scenario | None:
    """The focus with the best plus-value over the stats of the object; None when no stat gives a rune."""
    actions = {line.action_id for line in effects.lines if line.action_id in base_runes}
    scenarios = [build_scenario(effects, coefficient, base_runes, price_of, hdv_price, {}, action)
                 for action in sorted(actions)]
    return max(scenarios, key=lambda scenario: scenario.value, default=None)
