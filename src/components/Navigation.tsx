import { ChevronDown, List, SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { PAGE_TITLES, PAGES, SECTIONS } from "../lib/sections";
import { REPOSITORY_URL } from "../lib/servers";
import type { Page } from "../lib/types";
import { ExternalLink } from "./ExternalLink";

const ICONS: Record<Page, ReactNode> = {
  logs: <List size={18} aria-hidden="true" />,
  settings: <SlidersHorizontal size={18} aria-hidden="true" />,
};

interface Props {
  page: Page;
  activeSection: string;
  appVersion: string;
  onPage: (page: Page) => void;
  onSection: (id: string) => void;
}

/** The left rail: the pages, and under the current one a drawer with a sub menu per title. */
export function Rail({ page, activeSection, appVersion, onPage, onSection }: Props) {
  return (
    <aside className="rail">
      <div className="brand">
        <ExternalLink href={REPOSITORY_URL} className="brand-name">OpenDofusData</ExternalLink>
      </div>
      <nav className="nav" aria-label="Navigation principale">
        {PAGES.map((target) => (
          <div key={target}>
            <button
              type="button"
              className="nav-item"
              aria-current={target === page ? "page" : undefined}
              onClick={() => onPage(target)}
            >
              {ICONS[target]}
              {PAGE_TITLES[target]}
              <ChevronDown className={`chev-d${target === page ? " open" : ""}`} size={14} aria-hidden="true" />
            </button>
            {target === page ? (
              <ul className="drawer" aria-label={`Sections de ${PAGE_TITLES[target]}`}>
                {SECTIONS[target].map((section) => (
                  <li key={section.id}>
                    <button
                      type="button"
                      aria-current={section.id === activeSection ? "location" : undefined}
                      onClick={() => onSection(section.id)}
                    >
                      {section.title}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </nav>
      <div className="rail-foot">Version {appVersion}</div>
    </aside>
  );
}

/** The bottom tab bar of a narrow window. */
export function TabBar({ page, onPage }: Pick<Props, "page" | "onPage">) {
  return (
    <nav className="tabbar" aria-label="Navigation principale">
      {PAGES.map((target) => (
        <button key={target} type="button" aria-current={target === page ? "page" : undefined} onClick={() => onPage(target)}>
          {ICONS[target]}
          {PAGE_TITLES[target]}
        </button>
      ))}
    </nav>
  );
}

/** The section chips of a narrow window, in place of the drawer. */
export function SubNav({ page, activeSection, onSection }: Pick<Props, "page" | "activeSection" | "onSection">) {
  return (
    <div className="subnav" role="navigation" aria-label={`Sections de ${PAGE_TITLES[page]}`}>
      {SECTIONS[page].map((section) => (
        <button
          key={section.id}
          type="button"
          aria-current={section.id === activeSection ? "location" : undefined}
          onClick={() => onSection(section.id)}
        >
          {section.title}
        </button>
      ))}
    </div>
  );
}
