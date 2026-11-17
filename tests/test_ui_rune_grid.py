"""The rune table of the Brisage detail: header, one line per rune, then the totals."""

import pytest

pytest.importorskip("customtkinter")

import customtkinter

from opendofusdata.breaking_detail_text import DetailTab, Entry, Total
from opendofusdata.ui_rune_grid import RuneGrid
from opendofusdata.ui_theme import DOWN_COLOR, UP_COLOR

TAB = DetailTab("breaking", "Ce brisage", "il y a 2 j", ("Obtenu", "Attendu"),
                (Entry("Rune Do Feu", 1252.0, ("5", "4.5"), 6260.0), Entry("Rune Sa", None, ("2", "-"), None)),
                (Total("Runes obtenues", "6 260"), Total("Plus-value", "+5 941", True), Total("Perte", "-50", False)))


def labels(widget) -> list[customtkinter.CTkLabel]:
    found = []
    for child in widget.winfo_children():
        if isinstance(child, customtkinter.CTkLabel):
            found.append(child)
        found.extend(labels(child))
    return found


def texts(grid: RuneGrid) -> list[str]:
    return [label.cget("text") for label in labels(grid)]


def test_the_header_names_the_columns_then_each_rune_gets_its_figures(root) -> None:
    grid = RuneGrid(customtkinter.CTkFrame(root))
    grid.set_tab(TAB)
    shown = texts(grid)
    assert shown[:5] == ["Rune", "Prix", "Obtenu", "Attendu", "Valeur"]
    assert shown[5:10] == ["Rune Do Feu", "1 252", "5", "4.5", "6 260"]
    assert shown[10:15] == ["Rune Sa", "-", "2", "-", "-"]  # an unknown price or value shows a dash


def test_the_totals_follow_with_their_colour(root) -> None:
    grid = RuneGrid(customtkinter.CTkFrame(root))
    grid.set_tab(TAB)
    by_text = {label.cget("text"): label for label in labels(grid)}
    assert by_text["+5 941"].cget("text_color") == UP_COLOR and by_text["-50"].cget("text_color") == DOWN_COLOR
    assert "Runes obtenues" in by_text and "6 260" in by_text


def test_every_figure_column_is_right_aligned_and_the_name_left_aligned(root) -> None:
    grid = RuneGrid(customtkinter.CTkFrame(root))
    grid.set_tab(TAB)
    first_line = [label for label in labels(grid) if int(label.grid_info().get("row", -1)) == 1]
    assert [label.grid_info()["sticky"] for label in first_line] == ["w", "e", "e", "e", "e"]


def test_an_unchanged_tab_is_not_rebuilt_and_a_new_one_replaces_it(root) -> None:
    grid = RuneGrid(customtkinter.CTkFrame(root))
    grid.set_tab(TAB)
    first = labels(grid)
    grid.set_tab(TAB)
    assert labels(grid) == first
    grid.set_tab(DetailTab("balance", "Bilan", "", ("Total", "Par objet"), (), (Total("Objets brisés", "3"),)))
    assert "Aucune rune" in texts(grid) and "Objets brisés" in texts(grid)
