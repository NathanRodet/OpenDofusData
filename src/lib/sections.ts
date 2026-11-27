import type { Page } from "./types";

export interface Section {
  id: string;
  title: string;
}

export const PAGE_TITLES: Record<Page, string> = { logs: "Logs", settings: "Réglages" };

/** The sub menus of the left drawer (and the chips on a narrow window), one entry per title of the page. */
export const SECTIONS: Record<Page, readonly Section[]> = {
  logs: [
    { id: "connexion", title: "Connexion" },
    { id: "synchronisation", title: "Synchronisation" },
    { id: "messages", title: "Messages analysés" },
  ],
  settings: [
    { id: "serveur", title: "Serveur de synchronisation" },
    { id: "jeu", title: "Serveur de jeu" },
    { id: "cle", title: "Clé d'API" },
    { id: "journal", title: "Journal" },
    { id: "demarrage", title: "Démarrage" },
    { id: "dev", title: "Dev Mode - Capture" },
    { id: "maj", title: "Mises à jour et données" },
  ],
};

export const PAGES: readonly Page[] = ["logs", "settings"];

/** The ids of each page's sections, built once so the scroll spy keeps a stable list. */
export const SECTION_IDS: Record<Page, readonly string[]> = {
  logs: SECTIONS.logs.map((section) => section.id),
  settings: SECTIONS.settings.map((section) => section.id),
};
