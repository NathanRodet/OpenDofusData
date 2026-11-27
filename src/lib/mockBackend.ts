import type { Backend } from "./backend";
import { DEFAULT_SETTINGS } from "./settings";
import { SAMPLES } from "./sampleLogs";
import type { AppStatus, ConnectionTest, KeyState, LogEntry, Settings, SyncProgress, UpdateInfo } from "./types";

const STORAGE_KEY = "odd-client-settings";
const NPCAP_FLAG = "odd-mock-npcap";
const LOG_PERIOD_MS = 1800;
const APP_VERSION = "2.4.0";
const NEXT_VERSION = "2.4.1";
const UPDATE_STEP = 9;
const KEY_LIFETIME_DAYS = 5;
const REFERENCE_TOTAL = 21622;

let update: UpdateInfo | null = null;
let sent = 128;
let received = 1204;
let nextLogId = 1;

function readSettings(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<Settings>) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

/** The mock reads the key like the server would: a key containing "expired" or "refused" is rejected. */
function keyStateOf(apiKey: string): KeyState {
  if (apiKey.trim() === "") return "missing";
  if (apiKey.includes("expired")) return "expired";
  if (apiKey.includes("refused")) return "refused";
  return "valid";
}

function npcapMissing(): boolean {
  try {
    return localStorage.getItem(NPCAP_FLAG) === "missing";
  } catch {
    return false;
  }
}

function advanceUpdate(): void {
  if (update === null || update.progress === null || update.progress >= 100) return;
  const progress = Math.min(100, update.progress + UPDATE_STEP);
  const totalMb = update.totalMb ?? 9.7;
  update = { ...update, progress, downloadedMb: Math.round(totalMb * progress) / 100 };
}

export const mockBackend: Backend = {
  async loadSettings() {
    return readSettings();
  },

  async saveSettings(settings) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  },

  async getStatus(): Promise<AppStatus> {
    const key = keyStateOf(readSettings().apiKey);
    advanceUpdate();
    return {
      appVersion: APP_VERSION,
      npcap: npcapMissing() ? "missing" : "ok",
      key,
      keyExpiresInDays: key === "valid" ? KEY_LIFETIME_DAYS : null,
      connection: key === "valid" ? "connected" : "offline",
      latencyMs: key === "valid" ? 42 : null,
      update,
    };
  },

  async getSync(): Promise<SyncProgress> {
    const total = 512;
    sent = Math.min(total, sent + (Math.random() < 0.4 ? 1 : 0));
    received += Math.random() < 0.3 ? 1 : 0;
    return {
      reference: { done: REFERENCE_TOTAL, total: REFERENCE_TOTAL },
      sent: { done: sent, total, pending: total - sent, errors: 0 },
      received: { count: received, lastAt: new Date().toISOString() },
    };
  },

  async testConnection(settings): Promise<ConnectionTest> {
    const state = keyStateOf(settings.apiKey);
    const messages: Record<KeyState, ConnectionTest> = {
      valid: { ok: true, message: "Clé valide, connecté au serveur." },
      expired: { ok: false, message: "Clé expirée. Génère-en une nouvelle depuis ton espace." },
      refused: { ok: false, message: "Clé refusée par le serveur." },
      missing: { ok: false, message: "Colle d'abord ta clé d'API." },
    };
    return messages[state];
  },

  async checkUpdate() {
    update = { version: NEXT_VERSION, fileName: `open-dofus-data_v${NEXT_VERSION}.exe`, progress: null, downloadedMb: null, totalMb: 9.7 };
    return update;
  },

  async startUpdate() {
    if (update !== null) update = { ...update, progress: 0, downloadedMb: 0 };
  },

  async purgeLocalData() {
    sent = 0;
  },

  async saveLogs(entries) {
    const lines = entries.map((entry) => JSON.stringify(entry)).join("\n");
    const url = URL.createObjectURL(new Blob([lines], { type: "application/x-ndjson" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `logs-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.jsonl`;
    link.click();
    URL.revokeObjectURL(url);
  },

  async openCaptureFolder() {
    // In a browser there is no folder to open.
  },

  onLog(listener) {
    const timer = window.setInterval(() => {
      const sample = SAMPLES[Math.floor(Math.random() * SAMPLES.length)];
      const entry: LogEntry = { ...sample, id: nextLogId++, at: new Date().toISOString() };
      listener(entry);
    }, LOG_PERIOD_MS);
    return () => window.clearInterval(timer);
  },
};
