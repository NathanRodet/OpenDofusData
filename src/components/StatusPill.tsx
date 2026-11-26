import { pillView } from "../lib/pill";
import type { AppStatus } from "../lib/types";
import { ExternalLink } from "./ExternalLink";

export function StatusPill({ status, host }: { status: AppStatus | null; host: string }) {
  const view = pillView(status, host);
  return (
    <span className="pill" role="status">
      <span className={`dot ${view.tone}`} />
      <span className="pill-text">
        {view.text}
        {view.link ? (
          <>
            {" "}
            <ExternalLink href={view.link.href} className="pill-link">
              {view.link.label}
            </ExternalLink>
          </>
        ) : null}
      </span>
      {view.ping ? (
        <>
          <span className="sep" aria-hidden="true">-</span>
          <span className="ping">{view.ping}</span>
        </>
      ) : null}
    </span>
  );
}
