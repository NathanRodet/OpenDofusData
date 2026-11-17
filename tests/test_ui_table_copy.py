"""Clicking a table cell copies its text."""

import pytest

pytest.importorskip("customtkinter")

from opendofusdata import ui_table_copy
from opendofusdata.pets_texts import FAVORITE_MARK
from opendofusdata.ui_table_copy import CopyOnClick, cell_text
from opendofusdata.ui_table import Column, DataTable
from opendofusdata.table_model import TableRow


class Click:
    x, y = 5, 5


class FakeTree:
    """Answers like a Treeview: a region, a row, a column and the cells of that row."""

    def __init__(self, region: str, item: str, column: str, cells: dict[int, str]) -> None:
        self.region, self.item, self.column, self.cells = region, item, column, cells

    def identify_region(self, x: int, y: int) -> str:
        return self.region

    def identify_row(self, y: int) -> str:
        return self.item

    def identify_column(self, x: int) -> str:
        return self.column

    def set(self, item: str, column: int) -> str:
        return self.cells[column]


def test_the_text_of_the_clicked_cell_is_returned_without_the_favourite_star() -> None:
    tree = FakeTree("cell", "0", "#2", {0: "Fer", 1: FAVORITE_MARK + "Ortie"})
    assert cell_text(tree, Click()) == "Ortie"


@pytest.mark.parametrize("region, item, column", [("heading", "", "#1"), ("cell", "", "#1"), ("cell", "0", "")])
def test_nothing_is_copied_outside_the_cells(region: str, item: str, column: str) -> None:
    assert cell_text(FakeTree(region, item, column, {0: "Fer"}), Click()) == ""


def test_a_click_puts_the_cell_in_the_clipboard(root, monkeypatch) -> None:
    table = DataTable(root, [Column("Nom", 100)], lambda key: None, (0, False))
    table.set_rows([TableRow("a", ("Ortie",), ("ortie",), None)])
    monkeypatch.setattr(ui_table_copy, "cell_text", lambda tree, event: "Ortie")
    CopyOnClick(table._tree)._clicked(Click())
    assert root.clipboard_get() == "Ortie"
