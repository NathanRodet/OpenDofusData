"""Prices typed by the player (HDV price of an object, purchase price of a breaking), kept in config.json."""

import logging
from pathlib import Path

from opendofusdata.app_config import load_config, save_config

logger = logging.getLogger(__name__)

HDV_OVERRIDES_KEY = "hdv_price_overrides"
PURCHASE_PRICES_KEY = "purchase_prices"
THEORY_COEFFICIENTS_KEY = "theory_coefficients"
SUFFIX_FACTORS = {"k": 1_000, "m": 1_000_000}
SEPARATORS = (" ", " ", " ")


def parse_kamas(text: str) -> float | None:
    """A typed amount (`95000`, `95 000`, `1,5k`, `2m`); empty text is None; ValueError when unreadable."""
    cleaned = text.strip().lower()
    for separator in SEPARATORS:
        cleaned = cleaned.replace(separator, "")
    if not cleaned:
        return None
    factor = SUFFIX_FACTORS.get(cleaned[-1], 1)
    number = cleaned[:-1] if cleaned[-1] in SUFFIX_FACTORS else cleaned
    value = float(number.replace(",", ".")) * factor
    if value < 0:
        raise ValueError("a price cannot be negative")
    return value


def load_prices(config_path: Path, key: str) -> dict[str, float]:
    """The saved prices under a config key (entry name -> kamas); bad entries are ignored."""
    saved = load_config(config_path).get(key)
    if not isinstance(saved, dict):
        return {}
    return {name: float(price) for name, price in saved.items()
            if isinstance(price, (int, float)) and not isinstance(price, bool)}


def store_price(config_path: Path, key: str, entry: str, price: float | None) -> bool:
    """Save (or, with None, remove) one price; False (and a warning) when the file cannot be written."""
    config = load_config(config_path)
    prices = dict(config.get(key)) if isinstance(config.get(key), dict) else {}
    if price is None:
        prices.pop(entry, None)
    else:
        prices[entry] = price
    try:
        save_config(config_path, {**config, key: prices})
    except OSError as error:
        logger.warning("prix non enregistré : %s", error)
        return False
    return True
