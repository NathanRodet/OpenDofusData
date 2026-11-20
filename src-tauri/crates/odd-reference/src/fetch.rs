//! Reads the collections of DofusDB page by page, with a few tries for each page.

use std::time::Duration;

use serde::{Deserialize, Serialize};

use crate::client::{Entry, FIELDS, Item, Named, PAGE_SIZE, Page, ReferenceClient, unavailable};
use crate::error::ReferenceError;

const ATTEMPTS_PER_PAGE: u32 = 3;
const RETRY_DELAY: Duration = Duration::from_millis(500);
const ITEMS: &str = "items";
const ITEM_TYPES: &str = "item-types";
const SUPER_TYPES: &str = "item-super-types";

/// Everything that is downloaded: the names the interface shows.
///
/// Pets and the certificates of mounts are items: they are in `items`, their types in `item_types`.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Reference {
    /// Every item of the game: equipment, resources, pets, certificates of mounts...
    pub items: Vec<Item>,
    /// The types of items (a sword, a pet, a dragoturkey...).
    pub item_types: Vec<Named>,
    /// The big categories of the auction house (Equipment, Resources...).
    pub item_super_types: Vec<Named>,
}

/// How far the download is, shared by the three collections.
struct Progress<F> {
    done: u64,
    grand: u64,
    report: F,
}

impl ReferenceClient {
    /// Downloads every collection. `on_progress` receives the entries read so far and the total of all collections.
    pub async fn fetch_all(&self, on_progress: impl FnMut(u64, u64) + Send) -> Result<Reference, ReferenceError> {
        let grand = self.total(ITEMS).await? + self.total(ITEM_TYPES).await? + self.total(SUPER_TYPES).await?;
        let mut progress = Progress {
            done: 0,
            grand,
            report: on_progress,
        };
        let items = self.collection(ITEMS, &mut progress).await?;
        let types = self.collection(ITEM_TYPES, &mut progress).await?;
        let super_types = self.collection(SUPER_TYPES, &mut progress).await?;
        Ok(Reference {
            items: items.into_iter().map(into_item).collect(),
            item_types: types.into_iter().map(into_named).collect(),
            item_super_types: super_types.into_iter().map(into_named).collect(),
        })
    }

    async fn total(&self, route: &str) -> Result<u64, ReferenceError> {
        Ok(self.page_with_retries(route, 0, 0).await?.total)
    }

    async fn collection<F: FnMut(u64, u64) + Send>(
        &self,
        route: &str,
        progress: &mut Progress<F>,
    ) -> Result<Vec<Entry>, ReferenceError> {
        let mut entries = Vec::new();
        loop {
            let page = self.page_with_retries(route, entries.len() as u64, PAGE_SIZE).await?;
            let received = page.data.len() as u64;
            entries.extend(page.data);
            progress.done += received;
            (progress.report)(progress.done, progress.grand);
            if received == 0 || entries.len() as u64 >= page.total {
                return Ok(entries);
            }
            tokio::time::sleep(self.pause).await;
        }
    }

    async fn page_with_retries(&self, route: &str, skip: u64, limit: u64) -> Result<Page, ReferenceError> {
        let mut last = ReferenceError::Unavailable("no attempt".to_owned());
        for attempt in 0..ATTEMPTS_PER_PAGE {
            if attempt > 0 {
                tokio::time::sleep(RETRY_DELAY.min(self.pause.max(Duration::from_millis(1)) * 10)).await;
            }
            match self.page(route, skip, limit).await {
                Ok(page) => return Ok(page),
                Err(error) => last = error,
            }
        }
        Err(last)
    }

    async fn page(&self, route: &str, skip: u64, limit: u64) -> Result<Page, ReferenceError> {
        let mut url = self.base.clone();
        url.set_path(route);
        url.set_query(Some(&format!("$limit={limit}&$skip={skip}&{FIELDS}")));
        let response = self.http.get(url).send().await.map_err(unavailable)?;
        if !response.status().is_success() {
            return Err(ReferenceError::Unavailable(format!("status {}", response.status())));
        }
        response.json().await.map_err(unavailable)
    }
}

fn into_item(entry: Entry) -> Item {
    Item {
        id: entry.id,
        name: entry.name.fr,
        level: entry.level,
        type_id: entry.type_id,
    }
}

fn into_named(entry: Entry) -> Named {
    Named {
        id: entry.id,
        name: entry.name.fr,
    }
}
