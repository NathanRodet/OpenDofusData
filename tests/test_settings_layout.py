"""The Réglages page: titled sections of compact rows, readable colours, controls that are not oversized."""

import pytest

pytest.importorskip("customtkinter")

import customtkinter

from opendofusdata.local_data_card import AUTO_LABEL
from opendofusdata.page_settings import SECTION_TITLES, SettingsPage
from opendofusdata.settings_names import REFERENCE_BUTTON_WIDTH
from opendofusdata.settings_rows import SettingRow
from opendofusdata.ui_theme import (
    CARD_COLOR, COLUMN_WIDTH, COMPACT_BUTTON_HEIGHT, COMPACT_BUTTON_WIDTH, MUTED_COLOR, TEXT_COLOR, WINDOW_COLOR,
)
from tests.test_page_settings import make_context

MAX_CHECKBOX_LABEL = 48  # longer labels do not fit a row and get cut off (CTkCheckBox cannot wrap)
MIN_TEXT_CONTRAST = 4.5  # WCAG AA for normal text


def make_page(root, tmp_path) -> SettingsPage:
    return SettingsPage(root, make_context(tmp_path), lambda current: None)


def luminance(color: str) -> float:
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def rows_of(panel) -> list[SettingRow]:
    return [child for child in panel.pack_slaves() if isinstance(child, SettingRow)]


def empty_default_frames(widget) -> list:
    """Frames without content that still ask for the 200 px a CTkFrame has by default."""
    found = []
    for child in widget.winfo_children():
        if isinstance(child, customtkinter.CTkFrame) and not child.winfo_children() and child.winfo_reqheight() >= 200:
            found.append(child)
        found.extend(empty_default_frames(child))
    return found


def test_the_page_has_the_planned_sections_in_order(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    assert [title for title, _ in page.sections] == list(SECTION_TITLES)
    assert SECTION_TITLES == ("Capture", "Données de référence", "Synchronisation", "Application")
    assert len(page.section_headings) == len(SECTION_TITLES)


def test_every_section_is_a_panel_of_rows(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    counts = {title: len(rows_of(panel)) for title, panel in page.sections}
    assert counts == {"Capture": 2, "Données de référence": 2, "Synchronisation": 2, "Application": 3}


def test_rows_are_separated_by_a_divider_and_the_first_has_none(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    for title, panel in page.sections:
        children = panel.pack_slaves()
        assert isinstance(children[0], SettingRow), title
        assert len(children) == 2 * len(rows_of(panel)) - 1, title  # row, divider, row, divider, ... row


def test_secondary_text_is_readable_on_the_panel_and_on_the_window() -> None:
    assert contrast(MUTED_COLOR, CARD_COLOR) >= MIN_TEXT_CONTRAST + 1  # comfortable, not just compliant
    assert contrast(MUTED_COLOR, WINDOW_COLOR) >= MIN_TEXT_CONTRAST
    assert contrast(TEXT_COLOR, CARD_COLOR) >= 7


def test_buttons_of_the_page_are_compact(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    assert COMPACT_BUTTON_HEIGHT <= 30 and COMPACT_BUTTON_WIDTH <= 160
    for button in (page.names_card.button, page.sync_card.save_button, page.sync_card.test_button,
                   page.local_data_card.purge_button):
        assert button.cget("height") == COMPACT_BUTTON_HEIGHT
        assert button.cget("width") <= (REFERENCE_BUTTON_WIDTH if button is page.names_card.button
                                        else COMPACT_BUTTON_WIDTH)


def test_the_column_does_not_stretch_with_the_window(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    root.update_idletasks()
    for _, panel in page.sections:
        assert panel.winfo_reqwidth() <= COLUMN_WIDTH
        assert not empty_default_frames(panel)  # no empty frame left at its default 200 px


def test_the_automatic_purge_label_fits_in_a_row() -> None:
    assert len(AUTO_LABEL) <= MAX_CHECKBOX_LABEL


def test_all_the_cards_are_still_reachable_by_their_old_names(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    for name in ("server_menu", "database_label", "names_card", "prices_card", "sync_card", "local_data_card",
                 "update_switch", "updates_card", "about_card"):
        assert hasattr(page, name), name
