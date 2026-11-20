/** Shared types of the client UI. The backend (Rust commands later, a mock for now) fills them. */

export type Page = "logs" | "settings";

export interface Settings {
  serverUrl: string;
  gameServer: string;
  apiKey: string;
  logsEnabled: boolean;
}

export type NpcapState = "ok" | "missing";
export type KeyState = "missing" | "valid" | "expired" | "refused";
export type ConnectionKind = "connected" | "connecting" | "offline";

export interface UpdateInfo {
  version: string;
  fileName: string;
  /** 0 to 100 while downloading, null before the player starts it. */
  progress: number | null;
  downloadedMb: number | null;
  totalMb: number | null;
}

export interface AppStatus {
  appVersion: string;
  npcap: NpcapState;
  key: KeyState;
  keyExpiresInDays: number | null;
  connection: ConnectionKind;
  latencyMs: number | null;
  update: UpdateInfo | null;
}

export interface SyncProgress {
  reference: { done: number; total: number };
  sent: { done: number; total: number; pending: number; errors: number };
  received: { count: number; lastAt: string | null };
}

export type LogCategory = "hdv" | "brisage" | "other";
export type LogOrigin = "game" | "server";
export type LogStatus = "analyzed" | "ignored" | "error";

export interface LogEntry {
  id: number;
  /** ISO 8601 UTC. */
  at: string;
  origin: LogOrigin;
  category: LogCategory;
  status: LogStatus;
  summary: string;
  /** The exact object sent to, or received from, the server. */
  payload: unknown;
  /** What the payload is, shown above it (sent, received, waiting...). */
  payloadNote: string;
}

export interface ConnectionTest {
  ok: boolean;
  message: string;
}
