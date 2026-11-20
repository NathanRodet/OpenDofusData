import { useCallback, useEffect, useState } from "react";
import type { RefObject } from "react";

/** A section is "current" once its top has passed this distance (px) below the top of the scroll area. */
const ACTIVE_OFFSET_PX = 80;
const BOTTOM_TOLERANCE_PX = 2;

/**
 * Tracks which section of a scrolling page is current, and scrolls to one on request.
 * The current section is the last one whose top is above the offset; at the very bottom it is the last one.
 */
export function useScrollSpy(
  container: RefObject<HTMLElement | null>,
  ids: readonly string[],
  contentKey: string,
): { active: string; scrollTo: (id: string) => void } {
  const [active, setActive] = useState(ids[0] ?? "");

  useEffect(() => {
    const root = container.current;
    if (root === null) return undefined;
    const update = () => {
      const rootTop = root.getBoundingClientRect().top;
      let current = ids[0] ?? "";
      for (const id of ids) {
        const section = document.getElementById(id);
        if (section !== null && section.getBoundingClientRect().top - rootTop <= ACTIVE_OFFSET_PX) current = id;
      }
      const atBottom = root.scrollTop + root.clientHeight >= root.scrollHeight - BOTTOM_TOLERANCE_PX;
      if (atBottom && root.scrollTop > 0) current = ids[ids.length - 1] ?? current;
      setActive(current);
    };
    update();
    root.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      root.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [container, ids, contentKey]);

  const scrollTo = useCallback((id: string) => {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return { active, scrollTo };
}
