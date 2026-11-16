"""The texts of the Brisage detail panel: classic breaking and best focus, rune by rune."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from opendofusdata.breaking_scenarios import RuneLine, Scenario
from opendofusdata.ui_stats import StatRow
from opendofusdata.value_format import format_kamas, format_signed_kamas

UNKNOWN_PRICE = "prix inconnu"
LARGE_COUNT = 100
REAL_TITLE = "Runes obtenues"


@dataclass(frozen=True)
class DetailBlock:
    """A titled group of lines with a summary whose colour says if the plus-value is positive (None: neutral)."""

    title: str
    lines: tuple[StatRow, ...]
    summary: str
    positive: bool | None = None


def count_text(value: float) -> str:
    """A rune count with enough digits to tell 0.034 from 0 (three significant digits, whole above 100)."""
    return f"{value:.0f}" if value >= LARGE_COUNT else f"{value:.3g}"


def price_text(price: float | None) -> str:
    """A rune unit price, or that it is unknown."""
    return UNKNOWN_PRICE if price is None else f"{format_kamas(price)} l'unité"


def rune_row(line: RuneLine, name: str) -> StatRow:
    """One rune: its name and unit price, then the expected count (and the real mean when known) and the value."""
    real = "" if line.real is None else f" (réel ×{count_text(line.real)})"
    value = "" if line.value is None else f" → {format_kamas(line.value)}"
    return (f"{name} ({price_text(line.unit_price)})", f"×{count_text(line.expected)}{real}{value}", None)


def real_block(totals: Mapping[int, int], objects: int, price_of: Callable[[int], float | None],
               hdv_price: float | None, name_of: Callable[[int], str]) -> DetailBlock:
    """The runes really obtained over every breaking of the object, valued with today's rune prices."""
    ordered = sorted(totals.items(), key=lambda entry: -(entry[1] * (price_of(entry[0]) or 0.0)))
    lines = tuple((f"{name_of(rune)} ({price_text(price_of(rune))})",
                   f"×{count}" + ("" if price_of(rune) is None else f" → {format_kamas(count * price_of(rune))}"), None)
                  for rune, count in ordered) or (("Aucune rune obtenue", "", None),)
    value = sum(count * (price_of(rune) or 0.0) for rune, count in totals.items())
    summary = f"{objects} objet(s) brisé(s)\nRunes {format_kamas(value)}"
    if hdv_price is None:
        return DetailBlock(REAL_TITLE, lines, summary)
    gain = value - hdv_price * objects
    return DetailBlock(REAL_TITLE, lines, f"{summary}\nPlus-value {format_signed_kamas(gain)}", gain >= 0)


def block_of(title: str, scenario: Scenario, name_of: Callable[[int], str], note: str = "") -> DetailBlock:
    """A detail block for one scenario, runes with the best value first."""
    ordered = sorted(scenario.lines, key=lambda line: -(line.value or 0.0))
    lines = tuple(rune_row(line, name_of(line.rune_id)) for line in ordered) or (("Aucune rune", "", None),)
    partial = " (prix de rune manquant)" if scenario.partial else ""
    gain = "Plus-value inconnue (prix de l'objet inconnu)" if scenario.plus_value is None \
        else f"Plus-value {format_signed_kamas(scenario.plus_value)}"
    summary = f"Runes {format_kamas(scenario.value)}{partial}\n{gain}{note}"
    return DetailBlock(title, lines, summary, None if scenario.plus_value is None else scenario.plus_value >= 0)


def detail_blocks(classic: Scenario, focus: Scenario | None, name_of: Callable[[int], str]) -> list[DetailBlock]:
    """The classic block, then the focus on the most profitable stat when there is one."""
    blocks = [block_of("Brisage classique", classic, name_of)]
    if focus is not None and focus.focus_rune is not None:
        extra = "" if classic.plus_value is None or focus.plus_value is None \
            else f"\n{format_signed_kamas(focus.plus_value - classic.plus_value)} vs classique"
        blocks.append(block_of(f"Focus le plus rentable : {name_of(focus.focus_rune)}", focus, name_of, extra))
    return blocks
