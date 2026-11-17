"""The history list of the detail panels: date, what happened, value, aligned like the stat lists above it."""

import pytest

pytest.importorskip("customtkinter")

import customtkinter

from opendofusdata.ui_history import EMPTY_TEXT, HistoryList

ROWS = [("14/11 23:59", "Nomoon", "×557, +3756 XP"), ("14/11 20:10", "Dragodinde", "×12, +90 XP")]


def texts(history: HistoryList) -> list[str]:
    return [child.cget("text") for child in history.winfo_children() if isinstance(child, customtkinter.CTkLabel)]


def test_each_row_has_its_date_its_subject_and_its_value_in_three_columns(root) -> None:
    history = HistoryList(customtkinter.CTkFrame(root))
    history.set_rows(ROWS)
    assert history.rows == tuple(ROWS) and texts(history) == [part for row in ROWS for part in row]
    columns = {int(child.grid_info()["column"]) for child in history.winfo_children()}
    assert columns == {0, 1, 2}


def test_the_value_column_is_right_aligned_and_the_date_left_aligned(root) -> None:
    history = HistoryList(customtkinter.CTkFrame(root))
    history.set_rows(ROWS)
    by_column = {int(child.grid_info()["column"]): child.grid_info()["sticky"] for child in history.winfo_children()}
    assert by_column[0] == "w" and by_column[2] == "e"


def test_an_unchanged_list_is_not_rebuilt(root) -> None:
    history = HistoryList(customtkinter.CTkFrame(root))
    history.set_rows(ROWS)
    first = list(history.winfo_children())
    history.set_rows(list(ROWS))
    assert list(history.winfo_children()) == first


def test_an_empty_history_says_so(root) -> None:
    history = HistoryList(customtkinter.CTkFrame(root))
    history.set_rows(ROWS)
    history.set_rows([])
    assert texts(history) == [EMPTY_TEXT] and history.rows == ()
