"""The two kinds of shared events (breakings and pet upgrades): their table, columns and wire format."""

import json
from collections.abc import Callable, Mapping
from typing import NamedTuple

from opendofusdata.event_rules import valid_broken_event, valid_pet_event

PET_STATE_FIELDS = ("level", "experience", "experience_max", "prospection")  # the order stored locally


class EventKind(NamedTuple):
    """How one kind of event is stored locally and sent: `columns` are the stored columns, in the order the
    functions below read and write them."""

    name: str
    path: str
    table: str
    columns: tuple[str, ...]
    to_event: Callable[[tuple], dict[str, object]]
    to_values: Callable[[Mapping[str, object]], tuple]
    valid: Callable[[Mapping[str, object]], bool]


def _pairs_text(pairs: object) -> str:
    return json.dumps([list(pair) for pair in pairs])  # type: ignore[attr-defined]


def _state_text(state: Mapping[str, object]) -> str:
    return json.dumps({name: state[name] for name in PET_STATE_FIELDS})


def _broken_event(values: tuple) -> dict[str, object]:
    server, captured_at, item_id, quantity, coefficient, runes_json = values
    return {"server": server, "item_id": item_id, "quantity": quantity, "coefficient": coefficient,
            "runes": json.loads(runes_json), "observed_at": captured_at}


def _broken_values(event: Mapping[str, object]) -> tuple:
    return (event["server"], event["observed_at"], event["item_id"], event["quantity"], event["coefficient"],
            _pairs_text(event["runes"]))


def _pet_event(values: tuple) -> dict[str, object]:
    server, captured_at, pet_item_id, resources_json, before_json, after_json = values
    return {"server": server, "pet_item_id": pet_item_id, "resources": json.loads(resources_json),
            "before": json.loads(before_json), "after": json.loads(after_json), "observed_at": captured_at}


def _pet_values(event: Mapping[str, object]) -> tuple:
    return (event["server"], event["observed_at"], event["pet_item_id"], _pairs_text(event["resources"]),
            _state_text(event["before"]), _state_text(event["after"]))  # type: ignore[arg-type]


BROKEN = EventKind(
    "broken", "/brisages", "broken_items",
    ("server", "captured_at", "item_id", "quantity", "coefficient", "runes_json"),
    _broken_event, _broken_values, valid_broken_event)
PET = EventKind(
    "pet", "/familiers", "pet_feedings",
    ("server", "captured_at", "pet_item_id", "resources_json", "before_json", "after_json"),
    _pet_event, _pet_values, valid_pet_event)
EVENT_KINDS = (BROKEN, PET)
