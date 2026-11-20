import type { MouseEvent, ReactNode } from "react";
import { openExternal } from "../lib/openExternal";

interface Props {
  href: string;
  className?: string;
  children: ReactNode;
}

/** A link that opens in the system browser. */
export function ExternalLink({ href, className = "link", children }: Props) {
  const open = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    void openExternal(href);
  };
  return (
    <a className={className} href={href} onClick={open} rel="noopener noreferrer">
      {children}
    </a>
  );
}
