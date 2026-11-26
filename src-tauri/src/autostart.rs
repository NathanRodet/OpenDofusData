//! The Windows startup entry: it follows the "launch at startup" setting of the player.

use tauri::AppHandle;
use tauri_plugin_autostart::ManagerExt;

/// Makes the startup entry of Windows match `enabled`. Nothing is written when it already does.
///
/// # Errors
/// Returns a message for the player when the entry cannot be read or changed.
pub fn apply(app: &AppHandle, enabled: bool) -> Result<(), String> {
    let manager = app.autolaunch();
    let current = manager.is_enabled().map_err(|error| error.to_string())?;
    if current == enabled {
        return Ok(());
    }
    let changed = if enabled { manager.enable() } else { manager.disable() };
    changed.map_err(|error| error.to_string())
}
