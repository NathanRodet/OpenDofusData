"""Tests for the CSV export."""

import io

from opendofusdata.export import write_lot_prices_csv
from opendofusdata.storage import LotPrice


def test_export_writes_header_and_rows() -> None:
    output = io.StringIO()
    prices = [LotPrice(307, "Ilyzaelle", 1, 750, "2026-11-10T10:29:17Z"),
              LotPrice(307, "Ilyzaelle", 10, 5868, "2026-11-10T10:29:17Z")]
    write_lot_prices_csv(prices, output)
    assert output.getvalue().splitlines() == [
        "item_id,server,lot_size,price,captured_at",
        "307,Ilyzaelle,1,750,2026-11-10T10:29:17Z",
        "307,Ilyzaelle,10,5868,2026-11-10T10:29:17Z",
    ]
