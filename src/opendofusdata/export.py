"""CSV export of stored lot prices."""

import csv
from collections.abc import Iterable
from typing import TextIO

from opendofusdata.records import LotPrice

CSV_COLUMNS = ("item_id", "server", "lot_size", "price", "captured_at")


def write_lot_prices_csv(prices: Iterable[LotPrice], output: TextIO) -> None:
    """Write lot prices as CSV with a header row (open the file with newline='')."""
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for lot in prices:
        writer.writerow((lot.item_id, lot.server, lot.lot_size, lot.price, lot.captured_at))
