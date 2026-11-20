//! Looks for a newer release of the application and downloads its installer, checked against its SHA-256.
#![forbid(unsafe_code)]

mod download;
mod error;
mod release;
mod updater;
mod version;

pub use error::UpdateError;
pub use release::Release;
pub use updater::Updater;
pub use version::Version;
