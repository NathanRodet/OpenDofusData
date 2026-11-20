//! The reference data against a fake DofusDB, and its local copy.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use axum::Json;
use axum::Router;
use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::routing::get;
use odd_reference::{Named, Reference, ReferenceClient, ReferenceError, ReferenceStore, Snapshot};
use serde_json::{Value, json};

const TOTAL: usize = 120;
const TYPES: usize = 12;
const SUPER_TYPES: usize = 7;

fn total_of(route: &str) -> usize {
    match route {
        "items" => TOTAL,
        "item-types" => TYPES,
        _ => SUPER_TYPES,
    }
}

#[derive(Default)]
struct Fake {
    /// Pages (by skip) that fail this many times before answering.
    failures: Mutex<HashMap<usize, usize>>,
    requests: AtomicUsize,
}

async fn collection(
    State(fake): State<Arc<Fake>>,
    Path(route): Path<String>,
    Query(query): Query<HashMap<String, String>>,
) -> (StatusCode, Json<Value>) {
    fake.requests.fetch_add(1, Ordering::SeqCst);
    let total = total_of(&route);
    let skip: usize = query.get("$skip").and_then(|value| value.parse().ok()).unwrap_or(0);
    let limit: usize = query
        .get("$limit")
        .and_then(|value| value.parse().ok())
        .unwrap_or(50)
        .min(50);
    if let Some(left) = fake.failures.lock().unwrap().get_mut(&skip).filter(|left| **left > 0) {
        *left -= 1;
        return (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({})));
    }
    let data: Vec<Value> = (skip..total.min(skip + limit))
        .map(|index| json!({ "id": index + 1, "level": 10, "typeId": 6, "name": { "fr": format!("Nom {}", index + 1) }, "img": "x" }))
        .collect();
    (
        StatusCode::OK,
        Json(json!({ "total": total, "limit": limit, "skip": skip, "data": data })),
    )
}

async fn serve(fake: Arc<Fake>) -> String {
    let app = Router::new().route("/{route}", get(collection)).with_state(fake);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    url
}

fn client(url: &str) -> ReferenceClient {
    ReferenceClient::new(url, Duration::ZERO).unwrap()
}

#[tokio::test]
async fn every_collection_is_fetched_and_progress_reaches_the_grand_total() {
    let url = serve(Arc::default()).await;
    let mut seen = Vec::new();
    let all = client(&url)
        .fetch_all(|done, total| seen.push((done, total)))
        .await
        .unwrap();
    assert_eq!(
        (all.items.len(), all.item_types.len(), all.item_super_types.len()),
        (TOTAL, TYPES, SUPER_TYPES)
    );
    let first = &all.items[0];
    assert_eq!(
        (first.id, first.name.as_str(), first.level, first.type_id),
        (1, "Nom 1", 10, 6)
    );
    assert_eq!(
        all.item_super_types[0],
        Named {
            id: 1,
            name: "Nom 1".to_owned()
        }
    );
    let grand = (TOTAL + TYPES + SUPER_TYPES) as u64;
    assert_eq!(seen.last().copied(), Some((grand, grand)));
    assert!(
        seen.windows(2).all(|pair| pair[0].0 <= pair[1].0),
        "progress never goes back"
    );
}

#[tokio::test]
async fn a_page_that_fails_a_few_times_is_tried_again() {
    let fake = Arc::new(Fake::default());
    fake.failures.lock().unwrap().insert(50, 2);
    let url = serve(Arc::clone(&fake)).await;
    assert_eq!(client(&url).fetch_all(|_, _| {}).await.unwrap().items.len(), TOTAL);
    // 3 counts, 3 + 1 + 1 pages, and the 2 failures of the page at 50.
    assert_eq!(fake.requests.load(Ordering::SeqCst), 3 + 5 + 2);
}

#[tokio::test]
async fn a_page_that_keeps_failing_gives_up() {
    let fake = Arc::new(Fake::default());
    fake.failures.lock().unwrap().insert(0, usize::MAX);
    let url = serve(fake).await;
    assert!(matches!(
        client(&url).fetch_all(|_, _| {}).await,
        Err(ReferenceError::Unavailable(_))
    ));
}

fn folder(name: &str) -> std::path::PathBuf {
    let path = std::env::temp_dir().join(format!("odd-reference-test-{}-{name}", std::process::id()));
    let _ = std::fs::remove_dir_all(&path);
    path
}

#[tokio::test]
async fn the_local_copy_comes_back_as_it_was_saved() {
    let url = serve(Arc::default()).await;
    let reference = client(&url).fetch_all(|_, _| {}).await.unwrap();
    let store = ReferenceStore::new(folder("roundtrip"));
    assert!(store.load().is_none());
    store
        .save(&Snapshot {
            fetched_at: 1_000,
            reference: reference.clone(),
        })
        .unwrap();
    let loaded = store.load().unwrap();
    assert_eq!((loaded.fetched_at, loaded.reference), (1_000, reference));
}

#[test]
fn a_copy_is_stale_after_its_maximum_age() {
    let snapshot = Snapshot {
        fetched_at: 1_000,
        reference: Reference::default(),
    };
    assert!(!snapshot.is_stale(1_000 + 99, 100));
    assert!(snapshot.is_stale(1_000 + 100, 100));
}

#[tokio::test]
async fn a_damaged_copy_is_ignored_and_replaced_by_the_next_save() {
    let directory = folder("damaged");
    std::fs::create_dir_all(&directory).unwrap();
    std::fs::write(directory.join("reference.json"), b"{ not json").unwrap();
    let store = ReferenceStore::new(directory);
    assert!(store.load().is_none());
    store
        .save(&Snapshot {
            fetched_at: 5,
            reference: Reference::default(),
        })
        .unwrap();
    assert_eq!(store.load().unwrap().fetched_at, 5);
}

#[tokio::test]
async fn a_copy_saved_by_an_older_version_is_ignored() {
    let directory = folder("old");
    std::fs::create_dir_all(&directory).unwrap();
    std::fs::write(directory.join("reference.json"), br#"{"fetched_at":1,"items":[]}"#).unwrap();
    assert!(ReferenceStore::new(directory).load().is_none());
}
