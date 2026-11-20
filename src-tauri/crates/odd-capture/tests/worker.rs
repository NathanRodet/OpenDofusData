//! Finding Npcap and building the command that starts the capture worker.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::ffi::OsString;
use std::path::{Path, PathBuf};

use odd_capture::{find_npcap_directory, path_with_npcap, worker_command};

fn temp_dir(name: &str) -> PathBuf {
    let directory = std::env::temp_dir().join(format!("odd-capture-test-{}-{name}", std::process::id()));
    std::fs::create_dir_all(&directory).unwrap();
    directory
}

#[test]
fn the_first_directory_that_holds_wpcap_is_chosen() {
    let empty = temp_dir("empty");
    let installed = temp_dir("installed");
    std::fs::write(installed.join("wpcap.dll"), b"").unwrap();
    let found = find_npcap_directory(&[empty.clone(), installed.clone()]);
    assert_eq!(found, Some(installed));
    assert_eq!(find_npcap_directory(&[empty, PathBuf::from("does-not-exist")]), None);
}

#[test]
fn the_npcap_directory_goes_first_in_the_search_path() {
    let joined = path_with_npcap(Path::new("C:\\Npcap"), Some(&OsString::from("C:\\Windows;C:\\Tools"))).unwrap();
    let parts: Vec<PathBuf> = std::env::split_paths(&joined).collect();
    assert_eq!(
        parts,
        [
            PathBuf::from("C:\\Npcap"),
            PathBuf::from("C:\\Windows"),
            PathBuf::from("C:\\Tools")
        ]
    );
}

#[test]
fn a_missing_search_path_gives_only_the_npcap_directory() {
    let joined = path_with_npcap(Path::new("C:\\Npcap"), None).unwrap();
    assert_eq!(std::env::split_paths(&joined).count(), 1);
}

#[test]
fn the_worker_command_carries_the_search_path_with_npcap() {
    let command = worker_command(Path::new("worker.exe"), Some(Path::new("C:\\Npcap"))).unwrap();
    assert_eq!(command.get_program(), "worker.exe");
    let path = command
        .get_envs()
        .find(|(name, _)| *name == "PATH")
        .and_then(|(_, value)| value)
        .unwrap();
    assert!(std::env::split_paths(path).next().unwrap().ends_with("Npcap"));
}

#[test]
fn without_npcap_directory_the_command_keeps_the_inherited_path() {
    let command = worker_command(Path::new("worker.exe"), None).unwrap();
    assert!(command.get_envs().next().is_none());
}
