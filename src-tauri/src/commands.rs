//! The commands the interface calls. Each one hands over to the service.
#![allow(missing_docs)]

use std::path::Path;
use std::process::Command;

use odd_service::{AppStatus, ConnectionTest, LogEntry, Service, Settings, SyncProgress, UpdateInfo};
use tauri::{AppHandle, Manager, State};

use crate::autostart;

/// The installer made by Tauri (NSIS): `/P` shows a progress bar only, `/R` starts the application again.
const INSTALLER_ARGUMENTS: [&str; 2] = ["/P", "/R"];

#[tauri::command]
pub fn load_settings(service: State<'_, Service>) -> Settings {
    service.settings()
}

#[tauri::command]
pub async fn save_settings(app: AppHandle, service: State<'_, Service>, settings: Settings) -> Result<(), String> {
    // The startup entry first: when Windows refuses it, nothing is saved and the player sees why.
    autostart::apply(&app, settings.launch_at_startup)?;
    service.save_settings(settings).await.map_err(|error| error.to_string())
}

#[tauri::command]
pub fn get_status(service: State<'_, Service>) -> AppStatus {
    service.status()
}

#[tauri::command]
pub fn get_sync(service: State<'_, Service>) -> SyncProgress {
    service.sync()
}

#[tauri::command]
pub async fn test_connection(service: State<'_, Service>, settings: Settings) -> Result<ConnectionTest, String> {
    Ok(service.test_connection(settings).await)
}

#[tauri::command]
pub async fn check_update(service: State<'_, Service>) -> Result<Option<UpdateInfo>, String> {
    service.check_update().await.map_err(|error| error.to_string())
}

/// Downloads and checks the installer, starts it, then closes the application so the installer can replace it.
#[tauri::command]
pub async fn start_update(app: AppHandle, service: State<'_, Service>) -> Result<(), String> {
    let installer = service.start_update().await.map_err(|error| error.to_string())?;
    run_installer(&installer).map_err(|error| error.to_string())?;
    app.exit(0);
    Ok(())
}

fn run_installer(installer: &Path) -> std::io::Result<()> {
    Command::new(installer).args(INSTALLER_ARGUMENTS).spawn().map(|_| ())
}

#[tauri::command]
pub async fn purge_local_data(service: State<'_, Service>) -> Result<(), String> {
    service.purge().await.map_err(|error| error.to_string())
}

#[tauri::command]
pub fn save_logs(app: AppHandle, service: State<'_, Service>, entries: Vec<LogEntry>) -> Result<(), String> {
    let folder = app.path().document_dir().map_err(|error| error.to_string())?;
    service
        .save_logs(&entries, &folder)
        .map(|_| ())
        .map_err(|error| error.to_string())
}
