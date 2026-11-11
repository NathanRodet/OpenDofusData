"""Tests for the CSV export."""

import io

from opendofusdata.export import write_lot_prices_csv
from opendofusdata.storage import LotPrice


def test_export_writes_header_and_rows() -> None:
    output = io.StringIO()
    prices = [LotPrice(307, "Ilyzaelle", 1, 750, "2026-11-10T10:29:17Z"),
              LotPrice(307, "Ilyzaelle", 10, 5868, "2026-11-10T10:29:17Z")]
    write_lot_prices_csv(prices, output, lambda item_id: "Ailes de Moskito")
    assert output.getvalue().splitlines() == [
        "item_id,item_name,server,lot_size,price,captured_at",
        "307,Ailes de Moskito,Ilyzaelle,1,750,2026-11-10T10:29:17Z",
        "307,Ailes de Moskito,Ilyzaelle,10,5868,2026-11-10T10:29:17Z",
    ]
