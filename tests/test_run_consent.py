"""The run command must respect the per-category consent of config.json (deny by default)."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from opendofusdata import cli
from opendofusdata.recycling_store import recycling_events
from opendofusdata.storage import PriceStore
from tests.envelopes import FLOW_KEY, lot_envelope
from tests.test_recycling import OS_OF_CHAFER, OS_STACK, added, request, result

MOMENT = datetime(2026, 11, 11, 19, 18, 30, tzinfo=timezone.utc)
CLIENT_KEY = (FLOW_KEY[2], FLOW_KEY[3], FLOW_KEY[0], FLOW_KEY[1])
DATABASE = "consent.db"


def capture(pipeline, interface) -> None:
    pipeline.on_envelope(lot_envelope(), FLOW_KEY)
    pipeline.on_envelope(added(1000, OS_OF_CHAFER, OS_STACK), FLOW_KEY)
    pipeline.on_envelope(request(), CLIENT_KEY)
    pipeline.on_envelope(result(3), FLOW_KEY)
    raise KeyboardInterrupt


def run_with(enabled: list[str] | None) -> tuple[int, int]:
    """Run the CLI capture; return (stored lot prices, stored recyclings)."""
    if enabled is not None:
        Path(os.environ["OPENDOFUSDATA_CONFIG"]).write_text(json.dumps({"enabled_categories": enabled}),
                                                            encoding="utf-8")
    assert cli.run(["run", "--db", DATABASE, "--server", "Brial"], capture, lambda: MOMENT) == 0
    store = PriceStore(DATABASE)
    try:
        return len(store.latest_prices()), len(recycling_events(store.connection))
    finally:
        store.close()


def test_without_a_config_only_hdv_is_recorded() -> None:
    prices, recyclings = run_with(None)
    assert prices > 0
    assert recyclings == 0


def test_an_enabled_category_is_recorded_and_a_disabled_one_is_not() -> None:
    assert run_with(["recycling"]) == (0, 1)


def test_all_enabled_categories_are_recorded() -> None:
    prices, recyclings = run_with(["hdv", "recycling", "pets", "breaking"])
    assert prices > 0
    assert recyclings == 1


def test_a_corrupt_config_falls_back_to_hdv_only() -> None:
    Path(os.environ["OPENDOFUSDATA_CONFIG"]).write_text("{ not json", encoding="utf-8")
    prices, recyclings = run_with(None)
    assert prices > 0
    assert recyclings == 0
