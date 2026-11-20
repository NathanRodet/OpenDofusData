//! Reads the latest release and compares it with the running version.

use std::sync::Once;
use std::time::Duration;

use reqwest::{Client, Url};

use crate::error::UpdateError;
use crate::release::{Listing, Release, read_checksum, trusted};
use crate::version::Version;

const CONNECT_TIMEOUT: Duration = Duration::from_secs(10);
const READ_TIMEOUT: Duration = Duration::from_secs(20);
const USER_AGENT: &str = concat!("open-dofus-data/", env!("CARGO_PKG_VERSION"));
static CRYPTO_PROVIDER: Once = Once::new();

/// Looks for a newer release and downloads its installer.
#[derive(Debug, Clone)]
pub struct Updater {
    pub(crate) http: Client,
    pub(crate) releases: Url,
    current: Option<Version>,
}

impl Updater {
    /// An updater reading `releases_url` (the "latest release" address of the repository).
    pub fn new(releases_url: &str, current_version: &str) -> Result<Self, UpdateError> {
        let releases = Url::parse(releases_url).map_err(|_| UpdateError::InvalidAddress)?;
        if !matches!(releases.scheme(), "http" | "https") {
            return Err(UpdateError::InvalidAddress);
        }
        CRYPTO_PROVIDER.call_once(|| {
            // An error means a provider is already installed, which is fine.
            let _ = rustls::crypto::ring::default_provider().install_default();
        });
        let http = Client::builder()
            .connect_timeout(CONNECT_TIMEOUT)
            .read_timeout(READ_TIMEOUT)
            .user_agent(USER_AGENT)
            .build()
            .map_err(|error| UpdateError::Setup(error.to_string()))?;
        Ok(Self {
            http,
            releases,
            current: Version::parse(current_version),
        })
    }

    /// The newest release when it is newer than the running version, `None` when this one is up to date.
    pub async fn latest(&self) -> Result<Option<Release>, UpdateError> {
        let response = self.get(self.releases.clone()).await?;
        let listing: Listing = response.json().await.map_err(unavailable)?;
        let offered = Version::parse(&listing.tag_name);
        if offered.is_none() || offered <= self.current {
            return Ok(None);
        }
        let Some(installer) = listing.installer() else {
            return Ok(None);
        };
        let checksum = listing.checksum_of(installer).ok_or(UpdateError::MissingChecksum)?;
        let url = trusted(&installer.browser_download_url, &self.releases)?;
        let checksum_url = trusted(&checksum.browser_download_url, &self.releases)?;
        let text = self.get(checksum_url).await?.text().await.map_err(unavailable)?;
        Ok(Some(Release {
            version: listing.tag_name.trim_start_matches('v').to_owned(),
            file_name: installer.name.clone(),
            url: url.into(),
            size: installer.size,
            sha256: read_checksum(&text)?,
        }))
    }

    pub(crate) async fn get(&self, url: Url) -> Result<reqwest::Response, UpdateError> {
        let response = self.http.get(url).send().await.map_err(unavailable)?;
        let status = response.status();
        if status.is_success() {
            Ok(response)
        } else {
            Err(UpdateError::Unavailable(format!("status {status}")))
        }
    }
}

pub(crate) fn unavailable(error: reqwest::Error) -> UpdateError {
    UpdateError::Unavailable(error.without_url().to_string())
}
