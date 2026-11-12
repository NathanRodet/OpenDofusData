"""Every category is stored by the run command, whatever an old config.json says."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from opendofusdata import cli
from opendofusdata.breaking_store import broken_items
from opendofusdata.storage import PriceStore
from tests.envelopes import FLOW_KEY, lot_envelope
from tests.test_breaking import GA_PA, break_request, broken, outcome
from tests.window_messages import OS_OF_CHAFER, OS_STACK, added

MOMENT = datetime(2026, 11, 11, 19, 18, 30, tzinfo=timezone.utc)
CLIENT_KEY = (FLOW_KEY[2], FLOW_KEY[3], FLOW_KEY[0], FLOW_KEY[1])
DATABASE = "always.db"


def capture(pipeline, interface) -> None:
    pipeline.on_envelope(lot_envelope(), FLOW_KEY)
    pipeline.on_envelope(added(1, OS_OF_CHAFER, OS_STACK), FLOW_KEY)
    pipeline.on_envelope(break_request(), CLIENT_KEY)
    pipeline.on_envelope(broken(outcome(OS_STACK, ((3, GA_PA),))), FLOW_KEY)
    raise KeyboardInterrupt


def run_and_count() -> tuple[int, int]:
    """Run the CLI capture; return (stored lot prices, stored broken objects)."""
    assert cli.run(["run", "--db", DATABASE, "--server", "Brial"], capture, lambda: MOMENT) == 0
    store = PriceStore(DATABASE)
    try:
        return len(store.latest_prices()), len(broken_items(store.connection))
    finally:
        store.close()


def test_every_category_is_stored_without_any_config() -> None:
    prices, breakings = run_and_count()
    assert prices > 0
    assert breakings == 1


def test_enabled_categories_in_an_old_config_are_ignored() -> None:
    Path(os.environ["OPENDOFUSDATA_CONFIG"]).write_text(json.dumps({"enabled_categories": []}), encoding="utf-8")
    prices, breakings = run_and_count()
    assert prices > 0
    assert breakings == 1
