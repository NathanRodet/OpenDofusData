"""The texts of the Brisage detail panel: classic breaking and best focus, rune by rune."""

from collections.abc import Callable
from dataclasses import dataclass

from opendofusdata.breaking_scenarios import RuneLine, Scenario
from opendofusdata.value_format import format_kamas, format_signed_kamas

UNKNOWN_PRICE = "prix inconnu"


@dataclass(frozen=True)
class DetailBlock:
    """A titled group of lines with a summary whose colour says if the plus-value is positive (None: neutral)."""

    title: str
    lines: tuple[str, ...]
    summary: str
    positive: bool | None = None


def rune_text(line: RuneLine, name: str) -> str:
    """One rune: expected count (and the real mean when known), unit price and value."""
    real = "" if line.real is None else f" (réel ×{line.real:.1f})"
    price = UNKNOWN_PRICE if line.unit_price is None else f"{format_kamas(line.unit_price)} l'unité"
    value = "" if line.value is None else f" → {format_kamas(line.value)}"
    return f"{name} ×{line.expected:.1f}{real} · {price}{value}"


def block_of(title: str, scenario: Scenario, name_of: Callable[[int], str], note: str = "") -> DetailBlock:
    """A detail block for one scenario, runes with the best value first."""
    ordered = sorted(scenario.lines, key=lambda line: -(line.value or 0.0))
    lines = tuple(rune_text(line, name_of(line.rune_id)) for line in ordered) or ("Aucune rune",)
    partial = " (prix de rune manquant)" if scenario.partial else ""
    gain = "plus-value inconnue (prix de l'objet inconnu)" if scenario.plus_value is None \
        else f"plus-value {format_signed_kamas(scenario.plus_value)}"
    summary = f"Runes {format_kamas(scenario.value)}{partial} · {gain}{note}"
    return DetailBlock(title, lines, summary, None if scenario.plus_value is None else scenario.plus_value >= 0)


def detail_blocks(classic: Scenario, focus: Scenario | None, name_of: Callable[[int], str]) -> list[DetailBlock]:
    """The classic block, then the focus on the most profitable stat when there is one."""
    blocks = [block_of("Brisage classique", classic, name_of)]
    if focus is not None and focus.focus_rune is not None:
        extra = "" if classic.plus_value is None or focus.plus_value is None \
            else f" ({format_signed_kamas(focus.plus_value - classic.plus_value)} vs classique)"
        blocks.append(block_of(f"Focus le plus rentable : {name_of(focus.focus_rune)}", focus, name_of, extra))
    return blocks
