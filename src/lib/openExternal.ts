import { openUrl } from "@tauri-apps/plugin-opener";

/** Opens a link in the system browser (Tauri), or in a new tab when running in a plain browser. */
export async function openExternal(url: string): Promise<void> {
  try {
    await openUrl(url);
  } catch {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}
