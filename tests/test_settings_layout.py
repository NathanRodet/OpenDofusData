"""The Réglages page is organised in titled sections whose cards share the same width and height per row."""

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.local_data_card import AUTO_LABEL
from opendofusdata.page_settings import SECTION_TITLES, SettingsPage
from tests.test_page_settings import make_context

MAX_CHECKBOX_LABEL = 48  # longer labels do not fit a card and get cut off (CTkCheckBox cannot wrap)


def make_page(root, tmp_path) -> SettingsPage:
    return SettingsPage(root, make_context(tmp_path), lambda current: None)


def test_the_page_has_the_planned_sections_in_order(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    assert [title for title, _ in page.sections] == list(SECTION_TITLES)
    assert SECTION_TITLES == ("Capture", "Données de référence", "Synchronisation", "Application")


def test_every_section_has_a_heading_and_at_least_one_card(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    for title, cards in page.sections:
        assert cards, title
    assert len(page.section_headings) == len(SECTION_TITLES)


@pytest.mark.parametrize("width, expected", [(380, 1), (700, 1), (800, 2), (1654, 2)])
def test_columns_follow_the_width_but_never_exceed_two(root, tmp_path, width: int, expected: int) -> None:
    page = make_page(root, tmp_path)
    page.reflow(width)
    for title, cards in page.sections:
        columns = {card.grid_info()["column"] for card in cards}
        assert len(columns) <= expected, title
    assert max(card.grid_info()["column"] for _, cards in page.sections for card in cards) == expected - 1


def test_cards_of_a_row_stretch_to_the_same_height(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    page.reflow(1654)
    for _, cards in page.sections:
        for card in cards:
            assert set(card.grid_info()["sticky"]) == set("nsew")


def test_the_automatic_purge_label_fits_in_a_card() -> None:
    assert len(AUTO_LABEL) <= MAX_CHECKBOX_LABEL


def test_all_the_cards_are_still_reachable_by_their_old_names(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    for name in ("server_menu", "database_label", "names_card", "prices_card", "sync_card", "local_data_card",
                 "update_switch", "updates_card", "about_card"):
        assert hasattr(page, name), name
