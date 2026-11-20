//! Entry point of the OpenDofusData desktop application.
// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
#![forbid(unsafe_code)]

use std::process::ExitCode;

fn main() -> ExitCode {
    match open_dofus_data_client_lib::run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("OpenDofusData could not run: {error}");
            ExitCode::FAILURE
        }
    }
}
