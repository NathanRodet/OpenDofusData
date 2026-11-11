"""Read commands: prices, history, stats and CSV export, all reading an existing database."""

import argparse
import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path

from opendofusdata.capture_errors import EXIT_OK, fail
from opendofusdata.export import write_lot_prices_csv
from opendofusdata.storage import MARKET_PERIODS, LotPrice, MarketStats, PriceStore

COLUMN_SEPARATOR = "  "
PRICE_HEADERS = ("item", "server", "lot", "price", "captured_at (UTC)")
STATS_HEADERS = ("period", "median", "mean", "sold", "points", "last purchase (UTC)",
                 "data updated (UTC)")
NO_PRICES_MESSAGE = "Aucun prix enregistré pour cette sélection."
NO_STATS_MESSAGE = "Aucune statistique enregistrée pour l'objet {item_id}."


def format_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Render rows as left-aligned text columns under a header line."""
    cells = [[str(cell) for cell in row] for row in (headers, *rows)]
    widths = [max(len(row[index]) for row in cells) for index in range(len(headers))]
    lines = [COLUMN_SEPARATOR.join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()
             for row in cells]
    return "\n".join(lines)


def _price_row(lot: LotPrice) -> tuple[object, ...]:
    return (lot.item_id, lot.server, lot.lot_size, lot.price, lot.captured_at)


def _stats_row(stats: MarketStats) -> tuple[object, ...]:
    return (stats.period, stats.median, stats.mean, stats.sold_count, len(stats.points),
            stats.last_purchase_at, stats.server_updated_at)


def check_database_path(path: str) -> str | None:
    """Return a French problem description, or None when the path is an existing file."""
    if Path(path).is_dir():
        return f"{path} est un dossier, pas une base de données."
    if not Path(path).is_file():
        return f"Base de données introuvable : {path}"
    if Path(path).stat().st_size == 0:
        return f"{path} est vide, pas une base de données."
    return None


def with_store(arguments: argparse.Namespace, action: Callable[[PriceStore], int]) -> int:
    """Run an action on an existing database, never creating a missing one."""
    problem = check_database_path(arguments.db)
    if problem is not None:
        return fail(problem)
    try:
        store = PriceStore(arguments.db)
        try:
            return action(store)
        finally:
            store.close()
    except sqlite3.Error as error:
        return fail(f"Base de données illisible : {arguments.db} ({error})")


def _print_prices(prices: list[LotPrice]) -> int:
    if not prices:
        print(NO_PRICES_MESSAGE)
        return EXIT_OK
    print(format_table(PRICE_HEADERS, [_price_row(lot) for lot in prices]))
    return EXIT_OK


def prices_command(arguments: argparse.Namespace) -> int:
    """Print the latest price per item, server and lot size."""
    return with_store(arguments, lambda store: _print_prices(store.latest_prices(arguments.item)))


def history_command(arguments: argparse.Namespace) -> int:
    """Print every captured price of an item at one lot size."""
    return with_store(
        arguments,
        lambda store: _print_prices(store.price_history(arguments.item_id, arguments.lot)),
    )


def _latest_stats(store: PriceStore, item_id: int, periods: Sequence[str]) -> list[MarketStats]:
    histories = (store.market_stats_history(item_id, period) for period in periods)
    return [history[-1] for history in histories if history]


def _print_stats(item_id: int, stats: list[MarketStats]) -> int:
    if not stats:
        print(NO_STATS_MESSAGE.format(item_id=item_id))
        return EXIT_OK
    print(format_table(STATS_HEADERS, [_stats_row(entry) for entry in stats]))
    return EXIT_OK


def stats_command(arguments: argparse.Namespace) -> int:
    """Print the most recent stored market statistics per period."""
    periods = (arguments.period,) if arguments.period else MARKET_PERIODS
    return with_store(
        arguments,
        lambda store: _print_stats(arguments.item_id, _latest_stats(store, arguments.item_id, periods)),
    )


def _export(store: PriceStore, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        write_lot_prices_csv(store.iter_lot_prices(), file)
    print(f"Prix exportés dans {output}.")
    return EXIT_OK


def export_csv_command(arguments: argparse.Namespace) -> int:
    """Export every stored lot price to a CSV file."""
    return with_store(arguments, lambda store: _export(store, Path(arguments.output)))
