//! The settings of the player, kept in a file of the user's configuration folder.

use std::io;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::error::ServiceError;

/// The collector of the project.
pub const DEFAULT_SERVER_URL: &str = "opendofusdata.reseaudesentrepreneurs.fr";
/// The game server chosen until the player picks another.
pub const DEFAULT_GAME_SERVER: &str = "Kourial";
const FILE_NAME: &str = "settings.json";
const TEMPORARY_NAME: &str = "settings.json.tmp";

/// What the player can change. The names are those of the interface.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub struct Settings {
    /// Address of the collector, with or without `https://`.
    pub server_url: String,
    /// The game server the player plays on.
    pub game_server: String,
    /// The player's key. Without a key nothing is sent.
    pub api_key: String,
    /// Whether the logs are shown and kept.
    pub logs_enabled: bool,
    /// Whether the application starts with Windows. Off until the player turns it on.
    pub launch_at_startup: bool,
    /// Dev mode: every game message is written to files, with the bytes of its opaque fields (text included). Off until the player turns it on.
    pub dev_capture: bool,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            server_url: DEFAULT_SERVER_URL.to_owned(),
            game_server: DEFAULT_GAME_SERVER.to_owned(),
            api_key: String::new(),
            logs_enabled: true,
            launch_at_startup: false,
            dev_capture: false,
        }
    }
}

/// The file of the settings.
#[derive(Debug, Clone)]
pub struct SettingsStore {
    directory: PathBuf,
}

impl SettingsStore {
    /// A store in `directory`, created on the first save.
    pub fn new(directory: PathBuf) -> Self {
        Self { directory }
    }

    /// The saved settings, or the defaults when there is no usable file.
    pub fn load(&self) -> Settings {
        match std::fs::read_to_string(self.directory.join(FILE_NAME)) {
            Ok(text) => serde_json::from_str(&text).unwrap_or_else(|error| {
                tracing::warn!(%error, "the settings file is damaged, the defaults are used");
                Settings::default()
            }),
            Err(_) => Settings::default(),
        }
    }

    /// Saves the settings. The file is replaced in one step, so a crash never leaves it half written.
    pub fn save(&self, settings: &Settings) -> Result<(), ServiceError> {
        std::fs::create_dir_all(&self.directory)?;
        let temporary = self.directory.join(TEMPORARY_NAME);
        std::fs::write(&temporary, serde_json::to_vec_pretty(settings)?)?;
        std::fs::rename(temporary, self.directory.join(FILE_NAME))?;
        Ok(())
    }

    /// Deletes the saved settings.
    pub fn remove(&self) -> Result<(), ServiceError> {
        match std::fs::remove_file(self.directory.join(FILE_NAME)) {
            Err(error) if error.kind() != io::ErrorKind::NotFound => Err(error.into()),
            _ => Ok(()),
        }
    }
}

/// The address with its scheme: `https://` is added when the player wrote only the host.
pub fn normalize_server_url(text: &str) -> String {
    let text = text.trim();
    if text.starts_with("http://") || text.starts_with("https://") {
        text.to_owned()
    } else {
        format!("https://{text}")
    }
}
