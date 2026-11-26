//! The settings of the player, kept in a file of the user's configuration folder.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::path::PathBuf;

use odd_service::{Settings, SettingsStore, normalize_server_url};

fn folder(name: &str) -> PathBuf {
    std::env::temp_dir().join(format!("odd-settings-test-{}-{name}", std::process::id()))
}

fn player() -> Settings {
    Settings {
        server_url: "collector.example.org".to_owned(),
        game_server: "Dakal".to_owned(),
        api_key: "odd_secret".to_owned(),
        logs_enabled: false,
        launch_at_startup: true,
    }
}

#[test]
fn without_a_file_the_defaults_are_used() {
    let settings = SettingsStore::new(folder("missing")).load();
    assert_eq!(settings, Settings::default());
    assert_eq!(settings.game_server, "Kourial");
    assert_eq!(settings.server_url, "opendofusdata.reseaudesentrepreneurs.fr");
    assert!(settings.api_key.is_empty() && settings.logs_enabled);
    assert!(
        !settings.launch_at_startup,
        "the application does not start with Windows by default"
    );
}

#[test]
fn saved_settings_come_back_and_the_folder_is_created() {
    let store = SettingsStore::new(folder("round-trip").join("nested"));
    store.save(&player()).unwrap();
    assert_eq!(store.load(), player());
}

#[test]
fn the_file_uses_the_names_of_the_interface_and_leaves_no_temporary_file() {
    let directory = folder("names");
    let store = SettingsStore::new(directory.clone());
    store.save(&player()).unwrap();
    let text = std::fs::read_to_string(directory.join("settings.json")).unwrap();
    for name in ["serverUrl", "gameServer", "apiKey", "logsEnabled", "launchAtStartup"] {
        assert!(text.contains(name), "{name} in {text}");
    }
    let leftovers: Vec<_> = std::fs::read_dir(&directory).unwrap().filter_map(Result::ok).collect();
    assert_eq!(leftovers.len(), 1, "only settings.json remains");
}

#[test]
fn a_damaged_file_gives_the_defaults() {
    let directory = folder("damaged");
    std::fs::create_dir_all(&directory).unwrap();
    std::fs::write(directory.join("settings.json"), b"{ not json").unwrap();
    assert_eq!(SettingsStore::new(directory).load(), Settings::default());
}

#[test]
fn missing_fields_keep_their_default() {
    let directory = folder("partial");
    std::fs::create_dir_all(&directory).unwrap();
    std::fs::write(directory.join("settings.json"), br#"{"apiKey":"odd_x"}"#).unwrap();
    let settings = SettingsStore::new(directory).load();
    assert_eq!(settings.api_key, "odd_x");
    assert_eq!(settings.game_server, "Kourial");
    assert!(
        !settings.launch_at_startup,
        "an older file without the field keeps it off"
    );
}

#[test]
fn removing_the_settings_gives_the_defaults_again() {
    let store = SettingsStore::new(folder("remove"));
    store.save(&player()).unwrap();
    store.remove().unwrap();
    assert_eq!(store.load(), Settings::default());
    store.remove().unwrap();
}

#[test]
fn a_server_address_without_a_prefix_gets_https() {
    assert_eq!(
        normalize_server_url(" collector.example.org "),
        "https://collector.example.org"
    );
    assert_eq!(
        normalize_server_url("https://collector.example.org/"),
        "https://collector.example.org/"
    );
    assert_eq!(normalize_server_url("http://127.0.0.1:8080"), "http://127.0.0.1:8080");
}
