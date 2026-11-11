"""CLI command categories: show, enable or disable the collected data categories."""

import argparse
from collections.abc import Callable

from opendofusdata.app_config import default_config_path, load_config, save_config
from opendofusdata.capture_errors import EXIT_OK, fail
from opendofusdata.categories import (
    CATEGORIES, KNOWN_KEYS, CategorySettings, categories_from_config, config_with_categories,
)
from opendofusdata.commands import format_table

HEADERS = ("clé", "catégorie", "état")
ENABLED_TEXT = "activée"
DISABLED_TEXT = "désactivée"
SOON_SUFFIX = " (bientôt)"
UNKNOWN_MESSAGE = "Catégorie inconnue : {key}. Catégories : {known}."
UNAVAILABLE_MESSAGE = "La catégorie « {label} » n'est pas encore disponible (pas de décodeur)."
SAVE_FAILED_MESSAGE = "Impossible d'écrire la configuration {path} : {error}"


def add_categories_command(commands: argparse._SubParsersAction) -> None:
    """Register the categories command."""
    parser = commands.add_parser("categories", help="affiche, active ou désactive les catégories de données")
    parser.add_argument("--enable", action="append", default=[], metavar="CLÉ",
                        help="active une catégorie (répétable)")
    parser.add_argument("--disable", action="append", default=[], metavar="CLÉ",
                        help="désactive une catégorie (répétable)")


def _state_text(settings: CategorySettings, key: str, available: bool) -> str:
    text = ENABLED_TEXT if settings.is_enabled(key) else DISABLED_TEXT
    return text if available else text + SOON_SUFFIX


def _print_listing(settings: CategorySettings) -> None:
    rows = [(category.key, category.label, _state_text(settings, category.key, category.available))
            for category in CATEGORIES]
    print(format_table(HEADERS, rows))


def _problem_with(keys: list[str], enabling: bool) -> str | None:
    for key in keys:
        if key not in KNOWN_KEYS:
            return UNKNOWN_MESSAGE.format(key=key, known=", ".join(KNOWN_KEYS))
        category = next(item for item in CATEGORIES if item.key == key)
        if enabling and not category.available:
            return UNAVAILABLE_MESSAGE.format(label=category.label)
    return None


def _apply(settings: CategorySettings, arguments: argparse.Namespace) -> str | None:
    problem = _problem_with(arguments.enable, True) or _problem_with(arguments.disable, False)
    if problem is None:
        for key in arguments.enable:
            settings.set_enabled(key, True)
        for key in arguments.disable:
            settings.set_enabled(key, False)
    return problem


def categories_command(arguments: argparse.Namespace) -> int:
    """Show the categories, after applying --enable / --disable and saving them."""
    path = default_config_path()
    config = load_config(path)
    settings = categories_from_config(config)
    problem = _apply(settings, arguments)
    if problem is not None:
        return fail(problem)
    if arguments.enable or arguments.disable:
        try:
            save_config(path, config_with_categories(config, settings))
        except OSError as error:
            return fail(SAVE_FAILED_MESSAGE.format(path=path, error=error))
    _print_listing(settings)
    return EXIT_OK


CATEGORY_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {"categories": categories_command}
