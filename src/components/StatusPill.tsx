import type { AppStatus } from "../lib/types";

type Tone = "ok" | "warn" | "bad";

interface PillView {
  tone: Tone;
  text: string;
  ping: string | null;
}

/** What the top bar says about the application, most urgent problem first. */
export function pillView(status: AppStatus | null, host: string): PillView {
  if (status === null) return { tone: "warn", text: "Chargement", ping: null };
  if (status.npcap === "missing") return { tone: "bad", text: "Capture arrêtée", ping: null };
  if (status.key === "missing") return { tone: "warn", text: "Clé manquante", ping: null };
  if (status.key === "expired") return { tone: "bad", text: "Clé expirée", ping: null };
  if (status.key === "refused") return { tone: "bad", text: "Clé refusée", ping: null };
  if (status.connection === "connected") {
    return { tone: "ok", text: `Connecté à ${host}`, ping: status.latencyMs === null ? null : `${status.latencyMs} ms` };
  }
  return { tone: "warn", text: "Serveur injoignable", ping: null };
}

export function StatusPill({ status, host }: { status: AppStatus | null; host: string }) {
  const view = pillView(status, host);
  return (
    <span className="pill" role="status">
      <span className={`dot ${view.tone}`} />
      <span className="pill-text">{view.text}</span>
      {view.ping ? (
        <>
          <span className="sep" aria-hidden="true">-</span>
          <span className="ping">{view.ping}</span>
        </>
      ) : null}
    </span>
  );
}
