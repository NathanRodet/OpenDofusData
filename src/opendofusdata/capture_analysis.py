"""Find which message of a discovery log carries given on-screen values (pure, no GUI or network)."""

import json
import logging
from collections import defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PATH_SEPARATOR = "."
PACKED_MARKER = "#"
SKELETON_NAME = "NEW_MESSAGE_TYPE"
SKELETON_HEADER = '{name} = "{type}"  # {direction}, {count} occurrence(s)'
SKELETON_HIT = "# {value} trouvé au champ {paths}"
SKIPPED_LINE_MESSAGE = "ligne %d ignorée (pas un message du journal)"

IntegerPaths = dict[int, set[str]]
GroupKey = tuple[str, str]


@dataclass(frozen=True)
class ValueHit:
    """A wanted value and every field path where it was seen."""

    value: int
    paths: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    """A message type (in one direction) with what it carries of the wanted values."""

    type_name: str
    direction: str
    count: int
    baseline_count: int
    min_size: int
    max_size: int
    hits: tuple[ValueHit, ...]


def load_records(path: str) -> list[dict]:
    """Read a JSON Lines discovery log; blank and invalid lines are skipped (OSError propagates)."""
    records: list[dict] = []
    with open(path, encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            record = _parse_line(line)
            if record is None:
                logger.warning(SKIPPED_LINE_MESSAGE, line_number)
            else:
                records.append(record)
    return records


def _parse_line(line: str) -> dict | None:
    try:
        record = json.loads(line)
    except ValueError:
        return None
    return record if isinstance(record, dict) and "type" in record else None


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _walk(fields: Iterable[object], prefix: str, found: IntegerPaths) -> None:
    for item in fields:
        if not isinstance(item, dict) or not _is_integer(item.get("number")):
            continue
        path = prefix + str(item["number"])
        if _is_integer(item.get("value")):
            found[item["value"]].add(path)
        for index, packed in enumerate(item.get("packed", [])):
            if _is_integer(packed):
                found[packed].add(f"{path}{PACKED_MARKER}{index}")
        _walk(item.get("fields", []), path + PATH_SEPARATOR, found)


def integer_paths(record: dict) -> IntegerPaths:
    """Every integer of a message with the field paths where it appears ('1.2', '1.2#0' if packed)."""
    found: IntegerPaths = defaultdict(set)
    _walk(record.get("fields", []), "", found)
    return dict(found)


def _group(records: Iterable[dict]) -> dict[GroupKey, list[dict]]:
    groups: dict[GroupKey, list[dict]] = defaultdict(list)
    for record in records:
        groups[(str(record.get("type")), str(record.get("direction")))].append(record)
    return groups


def _hits_of(records: list[dict], wanted: Collection[int]) -> tuple[ValueHit, ...]:
    seen: IntegerPaths = defaultdict(set)
    for record in records:
        for value, paths in integer_paths(record).items():
            if value in wanted:
                seen[value] |= paths
    return tuple(ValueHit(value, tuple(sorted(seen[value]))) for value in sorted(seen))


def _sizes(records: list[dict]) -> tuple[int, int]:
    sizes = [record["size"] for record in records if _is_integer(record.get("size"))] or [0]
    return min(sizes), max(sizes)


def find_candidates(
    action: Iterable[dict], baseline: Iterable[dict], wanted: Collection[int],
) -> list[Candidate]:
    """Message types of the action capture, the most promising first.

    Order: most wanted values found, then types absent from the baseline, then the biggest
    surplus of occurrences over the baseline.
    """
    baseline_counts = {key: len(records) for key, records in _group(baseline).items()}
    candidates = []
    for (type_name, direction), records in _group(action).items():
        smallest, biggest = _sizes(records)
        candidates.append(Candidate(type_name, direction, len(records),
                                    baseline_counts.get((type_name, direction), 0),
                                    smallest, biggest, _hits_of(records, wanted)))
    return sorted(candidates, key=lambda item: (-len(item.hits), item.baseline_count > 0,
                                                -(item.count - item.baseline_count), item.type_name))


def skeleton(candidate: Candidate) -> str:
    """Constants to paste into messages.py once the message is confirmed against the screen."""
    lines = [SKELETON_HEADER.format(name=SKELETON_NAME, type=candidate.type_name,
                                    direction=candidate.direction, count=candidate.count)]
    lines += [SKELETON_HIT.format(value=hit.value, paths=" ou ".join(hit.paths)) for hit in candidate.hits]
    return "\n".join(lines)
