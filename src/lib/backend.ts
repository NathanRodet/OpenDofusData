import { mockBackend } from "./mockBackend";
import { insideTauri, tauriBackend } from "./tauriBackend";
import type { AppStatus, ConnectionTest, LogEntry, Settings, SyncProgress, UpdateInfo } from "./types";

/**
 * Everything the UI needs from the application core. Inside the application the Rust service answers with Tauri
 * commands; in a plain browser (development, tests) the mock answers with simulated data.
 */
export interface Backend {
  loadSettings(): Promise<Settings>;
  saveSettings(settings: Settings): Promise<void>;
  getStatus(): Promise<AppStatus>;
  getSync(): Promise<SyncProgress>;
  testConnection(settings: Settings): Promise<ConnectionTest>;
  checkUpdate(): Promise<UpdateInfo | null>;
  startUpdate(): Promise<void>;
  purgeLocalData(): Promise<void>;
  /** Saves every log line since the launch to a file chosen by the player. */
  saveLogs(entries: LogEntry[]): Promise<void>;
  /** Opens the folder where the dev mode capture writes its files. */
  openCaptureFolder(): Promise<void>;
  /** Calls the listener for each analysed message; returns the function that stops it. */
  onLog(listener: (entry: LogEntry) => void): () => void;
}

export const backend: Backend = insideTauri() ? tauriBackend : mockBackend;
