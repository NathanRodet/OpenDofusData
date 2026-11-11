"""CLI command analyze: which message of a discovery log carries the values read on screen."""

import argparse
from collections.abc import Callable

from opendofusdata.capture_analysis import Candidate, find_candidates, load_records, skeleton
from opendofusdata.capture_errors import EXIT_OK, fail
from opendofusdata.commands import format_table

DEFAULT_TOP = 10
SKELETON_COUNT = 3
HEADERS = ("type", "sens", "occurrences", "taille", "témoin", "valeurs trouvées")
BAD_VALUES_MESSAGE = ("--values attend des entiers séparés par des virgules (entre guillemets dans "
                      "PowerShell), par exemple \"33528,4,120\".")
UNREADABLE_MESSAGE = "Impossible de lire {path} : {error}"
EMPTY_MESSAGE = "Aucun message dans ce journal."
MISSING_MESSAGE = "Valeurs introuvables dans cette capture : {values}"
HINT_PACKED = ("Astuce : une liste de nombres compactés n'apparaît qu'avec --hex-types NOM lors de la "
               "capture (voir docs/new-categories.md).")


def parse_values(raw: str) -> frozenset[int]:
    """Parse '33528, 4,120' into integers; anything else is a usage error."""
    try:
        values = frozenset(int(part) for part in raw.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(BAD_VALUES_MESSAGE) from error
    return values


def add_analyze_command(commands: argparse._SubParsersAction) -> None:
    """Register the analyze command."""
    parser = commands.add_parser("analyze", help="trouve le message qui contient les valeurs lues à l'écran")
    parser.add_argument("log", help="journal discover de la capture avec l'action")
    parser.add_argument("--baseline", default=None, help="journal discover d'une capture témoin, sans l'action")
    parser.add_argument("--values", type=parse_values, default=frozenset(), metavar="NOMBRES",
                        help="nombres lus à l'écran (identifiant d'objet, quantités...), séparés par des virgules")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP, help="nombre de messages affichés")
    parser.add_argument("--skeleton", action="store_true",
                        help="affiche les constantes à reporter dans messages.py")


def _hits_text(candidate: Candidate) -> str:
    return " ; ".join(f"{hit.value}@{' ou '.join(hit.paths)}" for hit in candidate.hits)


def _row(candidate: Candidate) -> tuple[object, ...]:
    sizes = f"{candidate.min_size}-{candidate.max_size}"
    return (candidate.type_name, candidate.direction, candidate.count, sizes, candidate.baseline_count,
            _hits_text(candidate))


def _missing_values(candidates: list[Candidate], wanted: frozenset[int]) -> list[int]:
    found = {hit.value for candidate in candidates for hit in candidate.hits}
    return sorted(wanted - found)


def _print_report(candidates: list[Candidate], arguments: argparse.Namespace) -> None:
    print(format_table(HEADERS, [_row(candidate) for candidate in candidates[:arguments.top]]))
    missing = _missing_values(candidates, arguments.values)
    if missing:
        print(MISSING_MESSAGE.format(values=", ".join(str(value) for value in missing)))
        print(HINT_PACKED)
    if arguments.skeleton:
        for candidate in [item for item in candidates if item.hits][:SKELETON_COUNT]:
            print()
            print(skeleton(candidate))


def analyze_command(arguments: argparse.Namespace) -> int:
    """Rank the messages of a capture by how many of the wanted values they carry."""
    try:
        action = load_records(arguments.log)
        baseline = load_records(arguments.baseline) if arguments.baseline else []
    except OSError as error:
        return fail(UNREADABLE_MESSAGE.format(path=getattr(error, "filename", None) or arguments.log, error=error))
    if not action:
        print(EMPTY_MESSAGE)
        return EXIT_OK
    _print_report(find_candidates(action, baseline, arguments.values), arguments)
    return EXIT_OK


ANALYZE_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {"analyze": analyze_command}
