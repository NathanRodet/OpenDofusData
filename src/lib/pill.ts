import type { AppStatus } from "./types";

export type Tone = "ok" | "warn" | "bad";

/** A link inside the pill (the server host when connected). */
export interface PillLink {
  href: string;
  label: string;
}

export interface PillView {
  tone: Tone;
  text: string;
  link: PillLink | null;
  ping: string | null;
}

const plain = (tone: Tone, text: string): PillView => ({ tone, text, link: null, ping: null });

/** What the top bar says about the application, most urgent problem first. */
export function pillView(status: AppStatus | null, host: string): PillView {
  if (status === null) return plain("warn", "Chargement");
  if (status.npcap === "missing") return plain("bad", "Capture arrêtée");
  if (status.key === "missing") return plain("warn", "Clé manquante");
  if (status.key === "expired") return plain("bad", "Clé expirée");
  if (status.key === "refused") return plain("bad", "Clé refusée");
  if (status.connection === "connected") {
    const ping = status.latencyMs === null ? null : `${status.latencyMs} ms`;
    return { tone: "ok", text: "Connecté à", link: { href: `https://${host}`, label: host }, ping };
  }
  return plain("warn", "Serveur injoignable");
}
