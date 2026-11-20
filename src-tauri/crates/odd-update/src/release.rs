//! The part of a GitHub release this application reads.

use reqwest::Url;
use serde::Deserialize;

use crate::error::UpdateError;

const INSTALLER_PREFIX: &str = "open-dofus-data_v";
const INSTALLER_SUFFIX: &str = "_setup.exe";
const CHECKSUM_SUFFIX: &str = ".sha256";
const SHA256_HEX_LENGTH: usize = 64;

/// A newer version, with what is needed to download and check it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Release {
    /// The version offered, like `2.5.0`.
    pub version: String,
    /// The name of the installer.
    pub file_name: String,
    /// Where the installer is.
    pub url: String,
    /// Its size in bytes, when GitHub says.
    pub size: Option<u64>,
    /// Its SHA-256, in lowercase hexadecimal.
    pub sha256: String,
}

#[derive(Debug, Deserialize)]
pub(crate) struct Listing {
    pub(crate) tag_name: String,
    pub(crate) assets: Vec<Asset>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct Asset {
    pub(crate) name: String,
    pub(crate) browser_download_url: String,
    pub(crate) size: Option<u64>,
}

impl Listing {
    /// The installer of the release, named `open-dofus-data_v<version>_setup.exe` (a plain file name).
    pub(crate) fn installer(&self) -> Option<&Asset> {
        self.assets.iter().find(|asset| {
            asset.name.starts_with(INSTALLER_PREFIX)
                && asset.name.ends_with(INSTALLER_SUFFIX)
                && !asset.name.contains(['/', '\\'])
        })
    }

    /// The checksum file of `installer`.
    pub(crate) fn checksum_of(&self, installer: &Asset) -> Option<&Asset> {
        let wanted = format!("{}{CHECKSUM_SUFFIX}", installer.name);
        self.assets.iter().find(|asset| asset.name == wanted)
    }
}

/// Reads the first word of a `sha256sum` style file.
pub(crate) fn read_checksum(text: &str) -> Result<String, UpdateError> {
    let word = text.split_whitespace().next().unwrap_or_default().to_ascii_lowercase();
    if word.len() == SHA256_HEX_LENGTH && word.chars().all(|character| character.is_ascii_hexdigit()) {
        Ok(word)
    } else {
        Err(UpdateError::BadChecksum)
    }
}

/// Files come from https, or from the very origin the releases were read from (tests, mirrors).
pub(crate) fn trusted(url: &str, releases: &Url) -> Result<Url, UpdateError> {
    let parsed = Url::parse(url).map_err(|_| UpdateError::UntrustedUrl)?;
    if parsed.scheme() == "https" || parsed.origin() == releases.origin() {
        Ok(parsed)
    } else {
        Err(UpdateError::UntrustedUrl)
    }
}

#[cfg(test)]
mod tests {
    use super::read_checksum;

    #[test]
    fn a_checksum_file_is_read_in_both_common_layouts() {
        let hash = "a".repeat(64);
        assert_eq!(read_checksum(&format!("{hash}  file.exe\n")).ok(), Some(hash.clone()));
        assert_eq!(read_checksum(&hash.to_uppercase()).ok(), Some(hash));
        assert!(read_checksum("not a hash").is_err());
        assert!(read_checksum("").is_err());
    }
}
