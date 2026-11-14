"""Craft recipes: parsing the raw DofusDB data and reading/writing data/recipes.csv. No network."""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_RECIPES_FILE = "recipes.csv"
DEFAULT_RECIPES_PATH = "data/" + DEFAULT_RECIPES_FILE
RECIPES_CSV_HEADER = ("result_id", "ingredients")
PAIR_SEPARATOR = ";"
QUANTITY_SEPARATOR = ":"


@dataclass(frozen=True)
class Recipe:
    """One craft: the produced object and its (ingredient id, quantity) pairs."""

    result_id: int
    ingredients: tuple[tuple[int, int], ...]


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def recipe_of(raw: object) -> Recipe | None:
    """A recipe from one raw DofusDB entry, or None when it is malformed."""
    if not isinstance(raw, dict):
        return None
    result_id, ids, quantities = raw.get("resultId"), raw.get("ingredientIds"), raw.get("quantities")
    if not _is_count(result_id) or not isinstance(ids, list) or not isinstance(quantities, list):
        return None
    if not ids or len(ids) != len(quantities) or not all(map(_is_count, ids + quantities)):
        return None
    return Recipe(result_id, tuple(zip(ids, quantities)))


def build_recipes(raw_recipes: list[object]) -> list[Recipe]:
    """Valid recipes sorted by result id; the first recipe of an object wins."""
    recipes: dict[int, Recipe] = {}
    for raw in raw_recipes:
        recipe = recipe_of(raw)
        if recipe is not None:
            recipes.setdefault(recipe.result_id, recipe)
    return [recipes[key] for key in sorted(recipes)]


def recipe_rows(recipes: list[Recipe]) -> list[tuple[int, str]]:
    """The CSV rows of the recipes."""
    return [(recipe.result_id, PAIR_SEPARATOR.join(f"{item}{QUANTITY_SEPARATOR}{count}"
                                                  for item, count in recipe.ingredients)) for recipe in recipes]


def _parse_row(row: list[str]) -> Recipe:
    pairs = tuple(tuple(int(part) for part in pair.split(QUANTITY_SEPARATOR)) for pair in row[1].split(PAIR_SEPARATOR))
    return Recipe(int(row[0]), pairs)


def load_recipes(path: str | Path) -> list[Recipe]:
    """Read the recipes CSV; a missing or unreadable file gives no recipes."""
    try:
        with open(path, encoding="utf-8", newline="") as file:
            rows = list(csv.reader(file))[1:]
        return [_parse_row(row) for row in rows if row]
    except FileNotFoundError:
        return []
    except (OSError, ValueError, IndexError) as error:
        logger.warning("recettes illisibles dans %s (%s)", path, error)
        return []
