//! Downloads the installer beside its final name, checks it, and only then gives it that name.

use std::path::{Path, PathBuf};

use reqwest::Url;
use sha2::{Digest, Sha256};
use tokio::io::AsyncWriteExt;

use crate::error::UpdateError;
use crate::release::{Release, trusted};
use crate::updater::{Updater, unavailable};

/// No installer of this application is anywhere near this size.
const MAX_INSTALLER_BYTES: u64 = 300 * 1024 * 1024;
const PARTIAL_SUFFIX: &str = ".part";

impl Updater {
    /// Downloads `release` into `folder` and returns the path of the checked installer.
    ///
    /// `on_progress` receives the bytes downloaded so far and the total when known. A file that does not match its
    /// SHA-256 is deleted and refused.
    pub async fn download(
        &self,
        release: &Release,
        folder: &Path,
        mut on_progress: impl FnMut(u64, Option<u64>) + Send,
    ) -> Result<PathBuf, UpdateError> {
        let url = trusted(&release.url, &self.releases)?;
        tokio::fs::create_dir_all(folder).await?;
        let target = folder.join(&release.file_name);
        let partial = folder.join(format!("{}{PARTIAL_SUFFIX}", release.file_name));
        match self.fetch(url, &partial, &release.sha256, &mut on_progress).await {
            Ok(()) => {
                tokio::fs::rename(&partial, &target).await?;
                Ok(target)
            }
            Err(error) => {
                let _ = tokio::fs::remove_file(&partial).await;
                Err(error)
            }
        }
    }

    async fn fetch(
        &self,
        url: Url,
        partial: &Path,
        expected: &str,
        on_progress: &mut (impl FnMut(u64, Option<u64>) + Send),
    ) -> Result<(), UpdateError> {
        let mut response = self.get(url).await?;
        let total = response.content_length();
        if total.is_some_and(|size| size > MAX_INSTALLER_BYTES) {
            return Err(UpdateError::TooBig);
        }
        let mut file = tokio::fs::File::create(partial).await?;
        let (mut hasher, mut done) = (Sha256::new(), 0_u64);
        while let Some(chunk) = response.chunk().await.map_err(unavailable)? {
            done += chunk.len() as u64;
            if done > MAX_INSTALLER_BYTES {
                return Err(UpdateError::TooBig);
            }
            hasher.update(&chunk);
            file.write_all(&chunk).await?;
            on_progress(done, total);
        }
        file.flush().await?;
        drop(file);
        let actual: String = hasher.finalize().iter().map(|byte| format!("{byte:02x}")).collect();
        if actual == expected {
            Ok(())
        } else {
            Err(UpdateError::ChecksumMismatch)
        }
    }
}
