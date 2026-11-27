import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { Backend } from "./backend";
import type { AppStatus, ConnectionTest, LogEntry, Settings, SyncProgress, UpdateInfo } from "./types";

/** The event the Rust side sends for every new line of the logs. */
const LOG_EVENT = "odd-log";

/** The real backend: every call goes to a Tauri command of the Rust application. */
export const tauriBackend: Backend = {
  loadSettings: () => invoke<Settings>("load_settings"),
  saveSettings: (settings) => invoke<void>("save_settings", { settings }),
  getStatus: () => invoke<AppStatus>("get_status"),
  getSync: () => invoke<SyncProgress>("get_sync"),
  testConnection: (settings) => invoke<ConnectionTest>("test_connection", { settings }),
  checkUpdate: () => invoke<UpdateInfo | null>("check_update"),
  startUpdate: () => invoke<void>("start_update"),
  purgeLocalData: () => invoke<void>("purge_local_data"),
  saveLogs: (entries: LogEntry[]) => invoke<void>("save_logs", { entries }),
  openCaptureFolder: () => invoke<void>("open_capture_folder"),
  onLog(listener) {
    let stopped = false;
    let unlisten: (() => void) | null = null;
    void listen<LogEntry>(LOG_EVENT, (event) => listener(event.payload)).then((stop) => {
      if (stopped) stop();
      else unlisten = stop;
    });
    return () => {
      stopped = true;
      unlisten?.();
    };
  },
};

/** Whether the page runs inside the Tauri application (and not in a plain browser, as in development or tests). */
export function insideTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}
