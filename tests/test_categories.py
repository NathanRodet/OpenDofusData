"""Tests of the data categories: config parsing, toggling and the filtering writer."""

from opendofusdata.categories import (
    CATEGORIES, CATEGORY_HDV, ENABLED_KEY, CategorySettings, FilteringWriter,
    categories_from_config, config_with_categories,
)
from opendofusdata.records import LotPrice


def make_lot() -> LotPrice:
    return LotPrice(item_id=307, server="Brial", lot_size=1, price=750, captured_at="2026-11-11T10:00:00Z")


class ListSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    def submit(self, record: object) -> None:
        self.records.append(record)


def test_default_is_hdv_only() -> None:
    assert categories_from_config({}).enabled_keys() == [CATEGORY_HDV]


def test_invalid_config_value_falls_back_to_default() -> None:
    for invalid in ("hdv", 42, [1, 2], None):
        assert categories_from_config({ENABLED_KEY: invalid}).enabled_keys() == [CATEGORY_HDV]


def test_unknown_keys_are_ignored() -> None:
    settings = categories_from_config({ENABLED_KEY: ["hdv", "xyz"]})
    assert settings.enabled_keys() == [CATEGORY_HDV]


def test_empty_list_means_nothing_enabled() -> None:
    assert categories_from_config({ENABLED_KEY: []}).enabled_keys() == []


def test_set_enabled_round_trips_through_config() -> None:
    settings = categories_from_config({})
    settings.set_enabled(CATEGORY_HDV, False)
    config = config_with_categories({"server": "Brial"}, settings)
    assert config == {"server": "Brial", ENABLED_KEY: []}
    assert categories_from_config(config).is_enabled(CATEGORY_HDV) is False


def test_only_breaking_has_no_decoder_yet() -> None:
    assert [category.key for category in CATEGORIES if not category.available] == ["breaking"]
    assert [category.key for category in CATEGORIES] == ["hdv", "recycling", "breaking", "pets"]


def test_filtering_writer_drops_records_when_hdv_disabled() -> None:
    sink = ListSink()
    FilteringWriter(sink, CategorySettings([])).submit(make_lot())
    assert sink.records == []


def test_filtering_writer_forwards_when_enabled() -> None:
    sink, lot = ListSink(), make_lot()
    FilteringWriter(sink, CategorySettings([CATEGORY_HDV])).submit(lot)
    assert sink.records == [lot]
