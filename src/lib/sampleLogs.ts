import type { LogEntry } from "./types";

type Sample = Omit<LogEntry, "id" | "at">;

const SERVER = "Kourial";
const envelope = (kind: string, observedAt: string, data: unknown) => ({
  schema: 1,
  event_id: "0194f0e2-7c1a-7b3e-9d51-3f6c2a8e41b0",
  kind,
  observed_at: observedAt,
  game_server: SERVER,
  data,
});

/** Simulated messages for the mock backend, in the JSON format of docs/json-schemas.md. */
export const SAMPLES: Sample[] = [
  {
    origin: "game", category: "hdv", status: "analyzed",
    summary: "Dragodinde dorée, 62 offres, plus bas 5 988 K",
    payloadNote: "Objet envoyé au serveur",
    payload: envelope("hdv.lots", "2026-11-19T12:04:31Z", {
      item_id: 33018,
      offers: [{ offer_id: 58557, price: 5988, effects: [{ effect_id: 125, value: 400 }, { effect_id: 2821, current: 1, max: 200 }] }],
    }),
  },
  {
    origin: "game", category: "brisage", status: "analyzed",
    summary: "Cape du Bouftou, 3 runes, coefficient 50 %",
    payloadNote: "Objet envoyé au serveur",
    payload: envelope("brisage", "2026-11-19T12:04:27Z", {
      item: { id: 1481, quantity: 1, effects: [{ effect_id: 125, value: 111 }, { effect_id: 243, value: 1 }] },
      coefficient: 0.5,
      runes: [{ item_id: 1522, quantity: 38 }, { item_id: 1557, quantity: 1 }],
    }),
  },
  {
    origin: "game", category: "hdv", status: "analyzed",
    summary: "Os de Chafer, statistiques 24 h, 7 jours et 30 jours",
    payloadNote: "Objet envoyé au serveur",
    payload: envelope("hdv.stats", "2026-11-19T12:03:52Z", {
      item_id: 307,
      last_purchase_at: "2026-11-19T11:50:09Z",
      periods: {
        "24h": { median: 359, mean: 359, sold_count: 83 },
        "7d": { median: 521, mean: 486, sold_count: 15998 },
        "30d": { median: 540, mean: 523, sold_count: 61200 },
      },
      points: { hourly: [{ at: "2026-11-19T10:00:00Z", price: 568, quantity: 3 }], daily: [{ at: "2026-11-18T00:00:00Z", price: 540, quantity: 410 }] },
    }),
  },
  {
    origin: "server", category: "hdv", status: "analyzed",
    summary: "Dragodinde Rousse, plus bas 5 988 K (autre joueur)",
    payloadNote: "Objet reçu du serveur",
    payload: envelope("hdv.lots", "2026-11-19T12:04:11Z", { item_id: 33063, offers: [{ offer_id: 61002, price: 5988, effects: [{ effect_id: 125, value: 380 }] }] }),
  },
  {
    origin: "game", category: "hdv", status: "error",
    summary: "Serveur injoignable, nouvel essai dans 10 s",
    payloadNote: "Objet en attente d'envoi",
    payload: { ...envelope("hdv.lots", "2026-11-19T12:04:02Z", { item_id: 307, lots: [{ size: 1, price: 750 }] }) },
  },
  {
    origin: "game", category: "other", status: "ignored",
    summary: "Message non collecté",
    payloadNote: "Aucun objet envoyé",
    payload: envelope("other", "2026-11-19T12:03:48Z", { message: "kpy", bytes: 237 }),
  },
];
