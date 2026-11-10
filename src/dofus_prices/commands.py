"""Read commands: prices, history, stats and CSV export, all reading an existing database."""

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from dofus_prices.capture_errors import EXIT_OK, fail
from dofus_prices.export import write_lot_prices_csv
from dofus_prices.storage import MARKET_PERIODS, LotPrice, MarketStats, PriceStore

COLUMN_SEPARATOR = "  "
PRICE_HEADERS = ("item", "server", "lot", "price", "captured_at (UTC)")
STATS_HEADERS = ("period", "median", "mean", "sold", "points", "last purchase (UTC)",
                 "data updated (UTC)")
NO_PRICES_MESSAGE = "Base vide : aucun prix enregistré."
NO_STATS_MESSAGE = "Base sans donnée : aucune statistique enregistrée pour l'objet {item_id}."


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


def _with_store(arguments: argparse.Namespace, action: Callable[[PriceStore], int]) -> int:
    """Run an action on an existing database, never creating a missing one."""
    if not Path(arguments.db).is_file():
        return fail(f"Base de données introuvable : {arguments.db}")
    store = PriceStore(arguments.db)
    try:
        return action(store)
    finally:
        store.close()


def _print_prices(prices: list[LotPrice]) -> int:
    if not prices:
        print(NO_PRICES_MESSAGE)
        return EXIT_OK
    print(format_table(PRICE_HEADERS, [_price_row(lot) for lot in prices]))
    return EXIT_OK


def prices_command(arguments: argparse.Namespace) -> int:
    """Print the latest price per item, server and lot size."""
    return _with_store(arguments, lambda store: _print_prices(store.latest_prices(arguments.item)))


def history_command(arguments: argparse.Namespace) -> int:
    """Print every captured price of an item at one lot size."""
    return _with_store(
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
    return _with_store(
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
    return _with_store(arguments, lambda store: _export(store, Path(arguments.output)))
