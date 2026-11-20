//! Saving the logs in a file.

use std::path::{Path, PathBuf};

use time::OffsetDateTime;

use crate::dto::LogEntry;
use crate::error::ServiceError;
use crate::service::Service;

impl Service {
    /// Writes the lines of the logs in a file of `folder`; returns the file.
    pub fn save_logs(&self, entries: &[LogEntry], folder: &Path) -> Result<PathBuf, ServiceError> {
        std::fs::create_dir_all(folder)?;
        let now = OffsetDateTime::now_utc();
        let name = format!(
            "OpenDofusData-logs-{:04}{:02}{:02}-{:02}{:02}{:02}.json",
            now.year(),
            u8::from(now.month()),
            now.day(),
            now.hour(),
            now.minute(),
            now.second()
        );
        let file = folder.join(name);
        std::fs::write(&file, serde_json::to_vec_pretty(entries)?)?;
        Ok(file)
    }
}
