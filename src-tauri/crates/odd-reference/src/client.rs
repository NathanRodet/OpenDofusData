//! The HTTP client of DofusDB and the shapes of what it answers.

use std::sync::Once;
use std::time::Duration;

use reqwest::{Client, Url};
use serde::{Deserialize, Serialize};

use crate::error::ReferenceError;

/// DofusDB never sends more than this many entries per request.
pub(crate) const PAGE_SIZE: u64 = 50;
const CONNECT_TIMEOUT: Duration = Duration::from_secs(10);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);
const USER_AGENT: &str = concat!("open-dofus-data/", env!("CARGO_PKG_VERSION"));
/// Only what the interface needs: the identifier, the French name, the level and the type.
pub(crate) const FIELDS: &str = "$select[]=id&$select[]=name.fr&$select[]=level&$select[]=typeId&$sort[id]=1";
static CRYPTO_PROVIDER: Once = Once::new();

/// An item of the game: what the interface needs to name it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Item {
    /// The identifier used in the game messages.
    pub id: i64,
    /// The French name.
    pub name: String,
    /// The level of the item.
    pub level: i64,
    /// The identifier of its type.
    pub type_id: i64,
}

/// Something that only has a name: a type of item, a category of the auction house.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Named {
    /// The identifier used in the game.
    pub id: i64,
    /// The French name.
    pub name: String,
}

#[derive(Deserialize)]
pub(crate) struct Page {
    pub(crate) total: u64,
    pub(crate) data: Vec<Entry>,
}

#[derive(Deserialize)]
pub(crate) struct Entry {
    pub(crate) id: i64,
    #[serde(default)]
    pub(crate) level: i64,
    #[serde(default, rename = "typeId")]
    pub(crate) type_id: i64,
    pub(crate) name: Name,
}

#[derive(Deserialize)]
pub(crate) struct Name {
    #[serde(default)]
    pub(crate) fr: String,
}

/// Reads the reference data of DofusDB.
#[derive(Debug, Clone)]
pub struct ReferenceClient {
    pub(crate) http: Client,
    pub(crate) base: Url,
    pub(crate) pause: Duration,
}

impl ReferenceClient {
    /// A client for the API at `base_url`; `pause` is the wait between two pages, to be kind to the API.
    pub fn new(base_url: &str, pause: Duration) -> Result<Self, ReferenceError> {
        let base = Url::parse(base_url).map_err(|_| ReferenceError::InvalidAddress)?;
        if !matches!(base.scheme(), "http" | "https") {
            return Err(ReferenceError::InvalidAddress);
        }
        CRYPTO_PROVIDER.call_once(|| {
            // An error means a provider is already installed, which is fine.
            let _ = rustls::crypto::ring::default_provider().install_default();
        });
        let http = Client::builder()
            .connect_timeout(CONNECT_TIMEOUT)
            .timeout(REQUEST_TIMEOUT)
            .user_agent(USER_AGENT)
            .build()
            .map_err(|error| ReferenceError::Setup(error.to_string()))?;
        Ok(Self { http, base, pause })
    }
}

pub(crate) fn unavailable(error: reqwest::Error) -> ReferenceError {
    ReferenceError::Unavailable(error.without_url().to_string())
}
