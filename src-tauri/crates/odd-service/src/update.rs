//! Looking for a newer version and downloading its installer.

use std::path::PathBuf;
use std::sync::{MutexGuard, PoisonError};

use odd_update::{Release, Updater};

use crate::dto::UpdateInfo;
use crate::error::ServiceError;
use crate::service::{Inner, Service};

const BYTES_PER_MEGABYTE: f32 = 1_048_576.0;
const PERCENT: u64 = 100;

/// A newer version, and how far its download is.
#[derive(Debug, Clone)]
pub(crate) struct Offer {
    release: Release,
    downloaded: Option<(u64, Option<u64>)>,
}

impl Offer {
    fn info(&self) -> UpdateInfo {
        let total = self.downloaded.and_then(|(_, total)| total).or(self.release.size);
        UpdateInfo {
            version: self.release.version.clone(),
            file_name: self.release.file_name.clone(),
            progress: self.downloaded.map(|(done, _)| percent(done, total)),
            downloaded_mb: self.downloaded.map(|(done, _)| megabytes(done)),
            total_mb: total.map(megabytes),
        }
    }
}

fn percent(done: u64, total: Option<u64>) -> u8 {
    match total {
        Some(total) if total > 0 => u8::try_from((done * PERCENT / total).min(PERCENT)).unwrap_or(100),
        _ => 0,
    }
}

#[allow(clippy::cast_precision_loss)]
fn megabytes(bytes: u64) -> f32 {
    bytes as f32 / BYTES_PER_MEGABYTE
}

impl Inner {
    fn offer(&self) -> MutexGuard<'_, Option<Offer>> {
        self.update.lock().unwrap_or_else(PoisonError::into_inner)
    }

    /// The update shown in the status, when there is one.
    pub(crate) fn offered_info(&self) -> Option<UpdateInfo> {
        self.offer().as_ref().map(Offer::info)
    }

    fn set_progress(&self, done: u64, total: Option<u64>) {
        if let Some(offer) = self.offer().as_mut() {
            offer.downloaded = Some((done, total));
        }
    }

    fn updater(&self) -> Result<Updater, ServiceError> {
        Ok(Updater::new(&self.config.releases_url, &self.config.app_version)?)
    }
}

impl Service {
    /// Asks GitHub for the latest release; keeps it as the offer when it is newer than this application.
    pub async fn check_update(&self) -> Result<Option<UpdateInfo>, ServiceError> {
        let latest = self.inner.updater()?.latest().await?;
        let mut offer = self.inner.offer();
        *offer = latest.map(|release| Offer {
            release,
            downloaded: None,
        });
        Ok(offer.as_ref().map(Offer::info))
    }

    /// Downloads the offered installer, checks it, and returns where it is.
    pub async fn start_update(&self) -> Result<PathBuf, ServiceError> {
        let release = self
            .inner
            .offer()
            .as_ref()
            .map(|offer| offer.release.clone())
            .ok_or(ServiceError::NoUpdate)?;
        self.inner.set_progress(0, release.size);
        let inner = std::sync::Arc::clone(&self.inner);
        let folder = self.inner.config.download_dir.clone();
        let updater = self.inner.updater()?;
        let path = updater
            .download(&release, &folder, move |done, total| inner.set_progress(done, total))
            .await;
        if path.is_err()
            && let Some(offer) = self.inner.offer().as_mut()
        {
            offer.downloaded = None;
        }
        Ok(path?)
    }
}
