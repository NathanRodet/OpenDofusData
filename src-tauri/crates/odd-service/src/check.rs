//! Checking the key with the collector, and what the interface says about it.

use std::time::Instant;

use odd_sync::{SyncClient, SyncError};
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

use crate::dto::ConnectionTest;
use crate::settings::normalize_server_url;

/// What the collector answered to a key check.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CheckResult {
    /// The key works.
    Valid {
        /// When it stops working, when the collector said so.
        expires_at: Option<OffsetDateTime>,
        /// How long the request took.
        latency_ms: u64,
    },
    /// The collector refuses the key.
    Refused,
    /// The collector cannot be reached.
    Unreachable,
    /// The address is not usable.
    InvalidAddress,
}

/// Asks the collector whether the key works.
pub async fn run_check(server_url: &str, key: &str) -> CheckResult {
    let Ok(client) = SyncClient::new(&normalize_server_url(server_url), key.trim()) else {
        return CheckResult::InvalidAddress;
    };
    let started = Instant::now();
    match client.check().await {
        Ok(info) => CheckResult::Valid {
            expires_at: OffsetDateTime::parse(&info.expires_at, &Rfc3339).ok(),
            latency_ms: u64::try_from(started.elapsed().as_millis()).unwrap_or(u64::MAX),
        },
        Err(SyncError::KeyRefused) => CheckResult::Refused,
        Err(_) => CheckResult::Unreachable,
    }
}

/// The sentence the player reads after pressing the test button.
pub fn test_message(result: &CheckResult) -> ConnectionTest {
    let (ok, message) = match result {
        CheckResult::Valid {
            expires_at: Some(date), ..
        } => (
            true,
            format!(
                "Connexion réussie, clé valide jusqu'au {:02}/{:02}/{}.",
                date.day(),
                u8::from(date.month()),
                date.year()
            ),
        ),
        CheckResult::Valid { expires_at: None, .. } => (true, "Connexion réussie, clé valide.".to_owned()),
        CheckResult::Refused => (false, "Le serveur refuse cette clé.".to_owned()),
        CheckResult::Unreachable => (false, "Impossible de joindre le serveur.".to_owned()),
        CheckResult::InvalidAddress => (false, "L'adresse du serveur n'est pas valide.".to_owned()),
    };
    ConnectionTest { ok, message }
}
