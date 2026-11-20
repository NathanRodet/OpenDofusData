//! The HTTP client of the collector.

use std::sync::Once;
use std::time::Duration;

use odd_core::Event;
use reqwest::{Client, Response, StatusCode, Url};
use serde::{Deserialize, Serialize};

const CONNECT_TIMEOUT: Duration = Duration::from_secs(5);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(15);
/// The client says its name and version, nothing else.
const USER_AGENT: &str = concat!("open-dofus-data/", env!("CARGO_PKG_VERSION"));

static CRYPTO_PROVIDER: Once = Once::new();

/// Why a request to the collector did not succeed.
#[derive(Debug, thiserror::Error)]
pub enum SyncError {
    /// The server address is not an http or https address.
    #[error("the server address is not a valid http or https address")]
    InvalidAddress,
    /// The HTTP client could not be prepared.
    #[error("cannot prepare the HTTP client: {0}")]
    Setup(String),
    /// The server does not accept the key: sending again will not help.
    #[error("the server refuses the key")]
    KeyRefused,
    /// The server refused the request itself: sending the same thing again will not help.
    #[error("the server refused the request (status {status})")]
    Refused {
        /// The HTTP status.
        status: u16,
    },
    /// The server cannot be reached or failed: sending again later may work.
    #[error("the server cannot be reached: {0}")]
    Unavailable(String),
}

/// What the server answers about a key.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
pub struct KeyInfo {
    /// Who the key was given to.
    pub label: String,
    /// When the key stops working (RFC 3339).
    pub expires_at: String,
}

/// What the server did with one object.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ServerStatus {
    /// It is now the freshest object of its slot.
    Stored,
    /// The server already holds a fresher object: nothing to do.
    Ignored,
    /// The server refuses this object, with its reason: do not send it again.
    Rejected(String),
    /// The server failed to store it: send it again later.
    Failed,
}

/// The server's answer for one object.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventResult {
    /// The `event_id` of the object.
    pub event_id: String,
    /// What the server did.
    pub status: ServerStatus,
}

#[derive(Serialize)]
struct Batch<'a> {
    events: &'a [Event],
}

#[derive(Deserialize)]
struct Answer {
    results: Vec<Entry>,
}

#[derive(Deserialize)]
struct Entry {
    event_id: String,
    status: String,
    reason: Option<String>,
}

/// Talks to the collector with the player's key.
#[derive(Debug, Clone)]
pub struct SyncClient {
    http: Client,
    base: String,
    key: String,
}

impl SyncClient {
    /// A client for the collector at `base_url`.
    pub fn new(base_url: &str, key: &str) -> Result<Self, SyncError> {
        let parsed = Url::parse(base_url.trim()).map_err(|_| SyncError::InvalidAddress)?;
        if !matches!(parsed.scheme(), "http" | "https") || parsed.host_str().is_none() {
            return Err(SyncError::InvalidAddress);
        }
        install_crypto_provider();
        let http = Client::builder()
            .connect_timeout(CONNECT_TIMEOUT)
            .timeout(REQUEST_TIMEOUT)
            .user_agent(USER_AGENT)
            .build()
            .map_err(|error| SyncError::Setup(error.to_string()))?;
        Ok(Self {
            http,
            base: parsed.as_str().trim_end_matches('/').to_owned(),
            key: key.to_owned(),
        })
    }

    /// Asks the server who the key is for and when it expires.
    pub async fn check(&self) -> Result<KeyInfo, SyncError> {
        let request = self.http.get(format!("{}/v1/check", self.base));
        let response = self.finish(request).await?;
        response
            .json()
            .await
            .map_err(|error| SyncError::Unavailable(error.to_string()))
    }

    /// Sends a batch of objects and returns the server's answer for each.
    pub async fn send(&self, events: &[Event]) -> Result<Vec<EventResult>, SyncError> {
        let request = self
            .http
            .post(format!("{}/v1/events", self.base))
            .json(&Batch { events });
        let answer: Answer = self
            .finish(request)
            .await?
            .json()
            .await
            .map_err(|error| SyncError::Unavailable(error.to_string()))?;
        Ok(answer.results.into_iter().map(into_result).collect())
    }

    async fn finish(&self, request: reqwest::RequestBuilder) -> Result<Response, SyncError> {
        let response = request
            .bearer_auth(&self.key)
            .send()
            .await
            .map_err(|error| SyncError::Unavailable(error.without_url().to_string()))?;
        classify(response.status()).map(|()| response)
    }
}

fn classify(status: StatusCode) -> Result<(), SyncError> {
    match status {
        status if status.is_success() => Ok(()),
        StatusCode::UNAUTHORIZED | StatusCode::FORBIDDEN => Err(SyncError::KeyRefused),
        StatusCode::REQUEST_TIMEOUT | StatusCode::TOO_MANY_REQUESTS => {
            Err(SyncError::Unavailable(format!("status {status}")))
        }
        status if status.is_server_error() => Err(SyncError::Unavailable(format!("status {status}"))),
        status => Err(SyncError::Refused {
            status: status.as_u16(),
        }),
    }
}

fn into_result(entry: Entry) -> EventResult {
    let status = match entry.status.as_str() {
        "stored" => ServerStatus::Stored,
        "ignored" => ServerStatus::Ignored,
        "rejected" => ServerStatus::Rejected(entry.reason.unwrap_or_default()),
        _ => ServerStatus::Failed,
    };
    EventResult {
        event_id: entry.event_id,
        status,
    }
}

/// TLS needs a cryptographic provider chosen once for the process. `ring` needs no C compiler.
fn install_crypto_provider() {
    CRYPTO_PROVIDER.call_once(|| {
        // An error means a provider is already installed, which is fine.
        let _ = rustls::crypto::ring::default_provider().install_default();
    });
}
