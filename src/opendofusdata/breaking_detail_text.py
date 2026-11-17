"""The tabs of the Brisage detail panel: this breaking, the balance of all of them, classic and focus.

Pure logic: every tab is a small table of runes (name, unit price, counts, value) and a few total lines.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from opendofusdata.breaking_scenarios import Scenario
from opendofusdata.breaking_texts import runes_text
from opendofusdata.breaking_view_data import BreakingRow
from opendofusdata.value_format import format_kamas, format_signed_kamas

LARGE_COUNT = 100
NO_COUNT = "-"
MISSING_PRICE_NOTE = " (prix de rune manquant)"
UNKNOWN_PLUS_VALUE = "inconnue (prix de l'objet inconnu)"
BREAKING_KEY, BALANCE_KEY, CLASSIC_KEY, FOCUS_KEY = "breaking", "balance", "classic", "focus"
PriceOf = Callable[[int], float | None]
NameOf = Callable[[int], str]


@dataclass(frozen=True)
class Entry:
    """One rune of a tab: its name, unit price, the texts of the count columns and the value of the line."""

    name: str
    price: float | None
    counts: tuple[str, ...]
    value: float | None


@dataclass(frozen=True)
class Total:
    """A summary line; `positive` colours a plus-value (None: neutral)."""

    label: str
    text: str
    positive: bool | None = None


@dataclass(frozen=True)
class DetailTab:
    """One tab: a short note, the headers of the count columns, the rune lines and the totals."""

    key: str
    title: str
    note: str
    headers: tuple[str, ...]
    entries: tuple[Entry, ...]
    totals: tuple[Total, ...]


def count_text(value: float) -> str:
    """A rune count with enough digits to tell 0.034 from 0 (three significant digits, whole above 100)."""
    return f"{value:.0f}" if value >= LARGE_COUNT else f"{value:.3g}"


def _best_value_first(entries: list[Entry]) -> tuple[Entry, ...]:
    return tuple(sorted(entries, key=lambda entry: -(entry.value or 0.0)))


def _plus_value_total(plus_value: float | None) -> Total:
    if plus_value is None:
        return Total("Plus-value", UNKNOWN_PLUS_VALUE)
    return Total("Plus-value", format_signed_kamas(plus_value), plus_value >= 0)


def breaking_tab(row: BreakingRow, scenario: Scenario | None, price_of: PriceOf, name_of: NameOf, note: str) -> DetailTab:
    """What one breaking gave, rune by rune, against what the classic formula expects for its coefficient."""
    obtained = dict(row.runes)
    expected = {line.rune_id: line.expected * row.quantity for line in scenario.lines} if scenario else {}
    entries = [Entry(name_of(rune), price_of(rune),
                     (str(obtained.get(rune, 0)), count_text(expected[rune]) if rune in expected else NO_COUNT),
                     None if price_of(rune) is None else obtained.get(rune, 0) * price_of(rune))
               for rune in sorted({*obtained, *expected})]
    totals = [Total("Runes obtenues", runes_text(row))]
    if scenario is not None:
        totals.append(Total("Valeur attendue", format_kamas(scenario.value * row.quantity)))
    if row.hdv_value is not None:
        totals.append(Total("Objet (HDV)", format_kamas(row.hdv_value)))
        totals.append(_plus_value_total(row.plus_value))
    return DetailTab(BREAKING_KEY, "Ce brisage", note, ("Obtenu", "Attendu"), _best_value_first(entries), tuple(totals))


def balance_tab(totals: Mapping[int, int], objects: int, price_of: PriceOf, hdv_price: float | None,
                name_of: NameOf) -> DetailTab:
    """The runes really obtained over every breaking of the object, valued with today's rune prices."""
    entries = [Entry(name_of(rune), price_of(rune), (str(count), count_text(count / objects) if objects else NO_COUNT),
                     None if price_of(rune) is None else count * price_of(rune)) for rune, count in totals.items()]
    value = sum(entry.value or 0.0 for entry in entries)
    lines = [Total("Objets brisés", str(objects)), Total("Runes obtenues", format_kamas(value))]
    if hdv_price is not None:
        lines.append(_plus_value_total(value - hdv_price * objects))
    return DetailTab(BALANCE_KEY, "Bilan", "", ("Total", "Par objet"), _best_value_first(entries), tuple(lines))


def scenario_tab(key: str, title: str, note: str, scenario: Scenario, name_of: NameOf,
                 versus: float | None = None) -> DetailTab:
    """A classic or focus breaking: the runes the formula expects (and the real mean when known)."""
    entries = [Entry(name_of(line.rune_id), line.unit_price,
                     (count_text(line.expected), NO_COUNT if line.real is None else count_text(line.real)), line.value)
               for line in scenario.lines]
    value = format_kamas(scenario.value) + (MISSING_PRICE_NOTE if scenario.partial else "")
    totals = [Total("Runes attendues", value), _plus_value_total(scenario.plus_value)]
    if versus is not None:
        totals.append(Total("Écart avec le classique", format_signed_kamas(versus), versus >= 0))
    return DetailTab(key, title, note, ("Attendu", "Réel moyen"), _best_value_first(entries), tuple(totals))
