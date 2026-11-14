"""The Brisage page: two tabs, the simulation (HDV price and potential kamas) and the purchases."""

import customtkinter

from opendofusdata.capture_session import SessionSnapshot
from opendofusdata.page_breaking_buys import PurchasesPage
from opendofusdata.page_breaking_sim import SimulationPage
from opendofusdata.page_breaking_theory import TheoryPage
from opendofusdata.ui_theme import PADDING, TRANSPARENT
from opendofusdata.window_context import WindowContext

TAB_SIMULATION = "Prix HDV et kamas potentiels"
TAB_PURCHASES = "Achats et résultats"
TAB_THEORY = "Brisage théorique"


class BreakingPage:
    """Switches between the two tabs; only the visible one reads the database."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        self.frame = customtkinter.CTkFrame(parent, fg_color=TRANSPARENT, corner_radius=0)
        self.tabs = customtkinter.CTkSegmentedButton(self.frame, values=[TAB_SIMULATION, TAB_PURCHASES, TAB_THEORY],
                                                     command=self.show_tab)
        self.tabs.pack(anchor="w", padx=PADDING, pady=(PADDING, 0))
        self.simulation = SimulationPage(self.frame, context, **options)
        self.purchases = PurchasesPage(self.frame, context, **options)
        self.theory = TheoryPage(self.frame, context, **options)
        self.current_tab = ""
        self.show_tab(TAB_SIMULATION)

    def _tab_page(self, name: str):
        return {TAB_SIMULATION: self.simulation, TAB_PURCHASES: self.purchases, TAB_THEORY: self.theory}[name]

    def show_tab(self, name: str) -> None:
        """Display one tab."""
        self.tabs.set(name)
        self.current_tab = name
        for page in (self.simulation, self.purchases, self.theory):
            page.frame.pack_forget()
        shown = self._tab_page(name)
        shown.frame.pack(fill="both", expand=True)
        shown.refresh()

    def render(self, snapshot: SessionSnapshot) -> None:
        """Refresh the visible tab."""
        self._tab_page(self.current_tab).render(snapshot)
