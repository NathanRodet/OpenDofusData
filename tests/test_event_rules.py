"""The bounds of the shared events, mirrored from the server so the client never sends or stores what it refuses."""

import pytest

from opendofusdata.event_rules import valid_broken_event, valid_pet_event

STATE = {"level": 5, "experience": 100, "experience_max": 200, "prospection": 10}


def broken(**changes: object) -> dict[str, object]:
    event: dict[str, object] = {"server": "Brial", "item_id": 1, "quantity": 2, "coefficient": 0.5,
                                "runes": [[10, 3], [11, 1]]}
    event.update(changes)
    return event


def pet(**changes: object) -> dict[str, object]:
    event: dict[str, object] = {"server": "Brial", "pet_item_id": 1, "resources": [[20, 4]],
                                "before": STATE, "after": {**STATE, "experience": 150}}
    event.update(changes)
    return event


def test_a_normal_broken_item_is_valid() -> None:
    assert valid_broken_event(broken())


@pytest.mark.parametrize("change", [
    {"quantity": 0}, {"quantity": True}, {"coefficient": -0.1}, {"coefficient": 11.0}, {"coefficient": "0.5"},
    {"item_id": 0}, {"server": "=cmd"}, {"runes": [[1, 2, 3]]}, {"runes": [[0, 1]]},
    {"runes": [[1, 0]]}, {"runes": [[1, 1]] * 41}, {"runes": "abc"}, {"runes": [[True, 1]]},
])
def test_a_bad_broken_item_is_not_valid(change: dict[str, object]) -> None:
    assert not valid_broken_event(broken(**change))


def test_a_normal_pet_feeding_is_valid_and_unknown_figures_may_be_null() -> None:
    assert valid_pet_event(pet())
    unknown = {"level": None, "experience": None, "experience_max": None, "prospection": None}
    assert valid_pet_event(pet(before=unknown))


@pytest.mark.parametrize("change", [
    {"pet_item_id": 0}, {"resources": []}, {"resources": [[1, 0]]}, {"server": ""},
    {"before": {"level": -1, "experience": 1, "experience_max": 1, "prospection": 1}},
    {"before": {"level": 1}}, {"after": {**STATE, "experience": 2**60}}, {"before": "x"},
    {"before": {**STATE, "extra": 1}},
])
def test_a_bad_pet_feeding_is_not_valid(change: dict[str, object]) -> None:
    assert not valid_pet_event(pet(**change))


def test_a_breaking_without_any_rune_is_valid_but_a_pet_upgrade_needs_a_resource() -> None:
    assert valid_broken_event(broken(runes=[]))
    assert not valid_pet_event(pet(resources=[]))
