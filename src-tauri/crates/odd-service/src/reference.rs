//! The reference data (items of DofusDB): kept on disk, refreshed when old, counted for the logs page.

use std::sync::{Arc, MutexGuard, PoisonError};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use odd_agent::problem;
use odd_reference::{Reference, ReferenceClient, ReferenceStore, Snapshot};

use crate::dto::Progress;
use crate::naming::Names;
use crate::service::Inner;

/// The copy is downloaded again after a week.
const MAX_AGE_SECONDS: u64 = 7 * 24 * 3600;
/// A pause between two pages keeps the load on DofusDB small.
const PAGE_PAUSE: Duration = Duration::from_millis(150);

/// How many items are known, and how many are expected.
#[derive(Debug, Default, Clone, Copy)]
pub(crate) struct Counter {
    pub(crate) done: u64,
    pub(crate) total: u64,
}

fn now_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|elapsed| elapsed.as_secs())
        .unwrap_or_default()
}

impl Inner {
    pub(crate) fn names(&self) -> MutexGuard<'_, Names> {
        self.names.lock().unwrap_or_else(PoisonError::into_inner)
    }

    fn know(&self, reference: &Reference) {
        let known = (reference.items.len() + reference.item_types.len() + reference.item_super_types.len()) as u64;
        *self.counter() = Counter {
            done: known,
            total: known,
        };
        *self.names() = Names {
            items: reference
                .items
                .iter()
                .map(|item| (item.id, item.name.clone()))
                .collect(),
            item_types: reference
                .item_types
                .iter()
                .map(|kind| (kind.id, kind.name.clone()))
                .collect(),
        };
    }

    pub(crate) fn counter(&self) -> MutexGuard<'_, Counter> {
        self.reference.lock().unwrap_or_else(PoisonError::into_inner)
    }

    /// The counter of the logs page.
    pub(crate) fn reference_progress(&self) -> Progress {
        let counter = *self.counter();
        Progress {
            done: counter.done,
            total: counter.total,
        }
    }

    fn reference_store(&self) -> ReferenceStore {
        ReferenceStore::new(self.config.config_dir.clone())
    }

    /// Forgets the local copy.
    pub(crate) fn forget_reference(&self) -> Result<(), odd_reference::ReferenceError> {
        *self.counter() = Counter::default();
        *self.names() = Names::default();
        self.reference_store().remove()
    }

    /// Uses the saved copy when it is recent, downloads the items otherwise.
    pub(crate) async fn refresh_reference(self: Arc<Self>) {
        let store = self.reference_store();
        if let Some(saved) = store.load() {
            self.know(&saved.reference);
            if !saved.is_stale(now_seconds(), MAX_AGE_SECONDS) {
                return;
            }
        }
        if let Err(reason) = self.download_reference(&store).await {
            tracing::warn!(%reason, "the reference data could not be downloaded");
            self.emit(&problem(
                "Les données de référence n'ont pas pu être téléchargées",
                &reason,
            ));
        }
    }

    async fn download_reference(&self, store: &ReferenceStore) -> Result<(), String> {
        let client = ReferenceClient::new(&self.config.reference_url, PAGE_PAUSE).map_err(|error| error.to_string())?;
        let reference = client
            .fetch_all(|done, total| *self.counter() = Counter { done, total })
            .await
            .map_err(|error| error.to_string())?;
        self.know(&reference);
        store
            .save(&Snapshot {
                fetched_at: now_seconds(),
                reference,
            })
            .map_err(|error| error.to_string())
    }
}
