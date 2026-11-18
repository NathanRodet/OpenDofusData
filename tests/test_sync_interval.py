"""The synchronisation interval setting: 10 to 300 seconds, 30 by default."""

import pytest

from opendofusdata.sync_interval import (
    DEFAULT_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS, MIN_INTERVAL_SECONDS, clamp_interval, load_sync_interval,
    save_sync_interval,
)
from opendofusdata.sync_options import load_sync_options

KEY = "odk1." + "A" * 11 + "." + "B" * 43


@pytest.mark.parametrize("value, expected", [(30, 30), (5, 10), (10, 10), (300, 300), (999, 300), (-4, 10),
                                              ("20", 30), (None, 30), (True, 30), (12.5, 30)])
def test_the_interval_is_clamped_and_anything_odd_gives_the_default(value, expected) -> None:
    assert clamp_interval(value) == expected


def test_the_defaults_are_the_agreed_ones() -> None:
    assert (MIN_INTERVAL_SECONDS, DEFAULT_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS) == (10, 30, 300)


def test_the_interval_is_saved_clamped_and_read_back(tmp_path) -> None:
    config = tmp_path / "config.json"
    assert load_sync_interval(config) == 30
    assert save_sync_interval(config, 90) and load_sync_interval(config) == 90
    assert save_sync_interval(config, 1) and load_sync_interval(config) == 10


def test_the_options_of_a_round_carry_the_saved_interval(tmp_path) -> None:
    from opendofusdata.sync_key import save_sync_key
    from opendofusdata.sync_server_url import save_server_url

    config = tmp_path / "config.json"
    save_sync_key(config, KEY)
    save_server_url(config, "serveur.exemple.fr")
    save_sync_interval(config, 45)
    options = load_sync_options(config, tmp_path / ".env")
    assert options is not None and options.interval == 45


def test_the_settings_slider_shows_the_saved_value_and_saves_a_new_one_in_steps_of_five(root, tmp_path) -> None:
    import customtkinter

    from opendofusdata.sync_interval_row import SyncIntervalRow
    from tests.view_page_helpers import make_context

    context = make_context(tmp_path)
    save_sync_interval(context.config_path, 60)
    frame = customtkinter.CTkFrame(root)
    frame.pack()
    row = SyncIntervalRow(frame, context)
    assert row.seconds() == 60 and row.value_label.cget("text") == "60 s"
    row.slider.set(200)
    row._moved(200)
    row.save()
    assert row.value_label.cget("text") == "200 s" and load_sync_interval(context.config_path) == 200
    row.slider.set(3)
    assert row.seconds() == 10
