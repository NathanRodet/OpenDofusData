//! The OpenDofusData desktop application: a thin Tauri shell around the service.
#![forbid(unsafe_code)]

mod commands;

use std::path::PathBuf;
use std::sync::Arc;

use odd_service::{LogEntry, Service, ServiceConfig, WorkerFactory};
use tauri::{Emitter, Manager, RunEvent};
use tracing_subscriber::EnvFilter;

/// The event the interface listens to for every new line of the logs.
const LOG_EVENT: &str = "odd-log";
const WORKER_FILE: &str = "odd-capture-worker.exe";
/// The public API of DofusDB, the source of the reference data.
const DOFUSDB_URL: &str = "https://api.dofusdb.fr";
const UPDATE_FOLDER: &str = "updates";
/// The latest release of the public repository (the code is visible, the releases too).
const RELEASES_URL: &str = "https://api.github.com/repos/NathanRodet/OpenDofusData/releases/latest";

/// Runs the application until its window is closed.
///
/// # Errors
/// Returns the error of Tauri when the application cannot start or stops abnormally.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() -> Result<(), tauri::Error> {
    init_logging();
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let service = start_service(app)?;
            app.manage(service);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::load_settings,
            commands::save_settings,
            commands::get_status,
            commands::get_sync,
            commands::test_connection,
            commands::check_update,
            commands::start_update,
            commands::purge_local_data,
            commands::save_logs,
        ])
        .build(tauri::generate_context!())?;
    app.run(|handle, event| {
        if let (RunEvent::Exit, Some(service)) = (event, handle.try_state::<Service>()) {
            tauri::async_runtime::block_on(service.shutdown());
        }
    });
    Ok(())
}

fn start_service(app: &tauri::App) -> Result<Service, Box<dyn std::error::Error>> {
    let config = ServiceConfig {
        config_dir: app.path().app_config_dir()?,
        download_dir: app.path().app_cache_dir()?.join(UPDATE_FOLDER),
        releases_url: RELEASES_URL.to_owned(),
        reference_url: DOFUSDB_URL.to_owned(),
        app_version: app.package_info().version.to_string(),
    };
    let handle = app.handle().clone();
    let emitter = Arc::new(move |entry: LogEntry| {
        if let Err(error) = handle.emit(LOG_EVENT, entry) {
            tracing::warn!(%error, "a log line could not reach the interface");
        }
    });
    let factory = Arc::new(WorkerFactory::new(worker_path()?));
    let runtime = tauri::async_runtime::handle().inner().clone();
    Ok(tauri::async_runtime::block_on(Service::start(
        config, runtime, factory, emitter,
    )))
}

/// The capture program sits next to the application.
fn worker_path() -> std::io::Result<PathBuf> {
    let executable = std::env::current_exe()?;
    Ok(executable.with_file_name(WORKER_FILE))
}

fn init_logging() {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    tracing_subscriber::fmt().with_env_filter(filter).init();
}
