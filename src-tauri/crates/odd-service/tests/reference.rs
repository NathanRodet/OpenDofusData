//! The reference data of the logs page: downloaded once, kept, shown as a counter.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use axum::Json;
use axum::Router;
use axum::extract::{Path, Query};
use axum::routing::get;
use odd_capture::FrameSource;
use odd_service::{NpcapState, Service, ServiceConfig, SourceError, SourceFactory};
use serde_json::{Value, json};

const ITEMS: usize = 60;
const TYPES: usize = 4;
const SUPER_TYPES: usize = 3;
/// Everything the service counts: items, types and super types.
const TOTAL: usize = ITEMS + TYPES + SUPER_TYPES;

struct NoCapture;

impl SourceFactory for NoCapture {
    fn npcap(&self) -> NpcapState {
        NpcapState::Missing
    }

    fn open(&self) -> Result<Box<dyn FrameSource>, SourceError> {
        Err(SourceError::NpcapMissing)
    }
}

async fn dofusdb() -> String {
    async fn items(Path(route): Path<String>, Query(query): Query<HashMap<String, String>>) -> Json<Value> {
        let total = match route.as_str() {
            "items" => ITEMS,
            "item-types" => TYPES,
            _ => SUPER_TYPES,
        };
        let skip: usize = query.get("$skip").and_then(|value| value.parse().ok()).unwrap_or(0);
        let data: Vec<Value> = (skip..total.min(skip + 50))
            .map(
                |index| json!({ "id": index + 1, "level": 1, "typeId": 2, "name": { "fr": format!("Objet {index}") } }),
            )
            .collect();
        Json(json!({ "total": total, "limit": 50, "skip": skip, "data": data }))
    }
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    tokio::spawn(async move {
        axum::serve(listener, Router::new().route("/{route}", get(items)))
            .await
            .unwrap()
    });
    url
}

fn folder(name: &str) -> PathBuf {
    let path = std::env::temp_dir().join(format!("odd-service-reference-{}-{name}", std::process::id()));
    let _ = std::fs::remove_dir_all(&path);
    path
}

async fn start(root: &std::path::Path, reference_url: String) -> Service {
    let config = ServiceConfig {
        config_dir: root.join("config"),
        download_dir: root.join("downloads"),
        app_version: "2.4.0".to_owned(),
        releases_url: "http://127.0.0.1:9/latest".to_owned(),
        reference_url,
    };
    Service::start(
        config,
        tokio::runtime::Handle::current(),
        Arc::new(NoCapture),
        Arc::new(|_| {}),
    )
    .await
}

async fn wait_for_total(service: &Service) {
    for _ in 0..500 {
        let reference = service.sync().reference;
        if reference.total == TOTAL as u64 && reference.done == reference.total {
            return;
        }
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
    panic!("the reference data never arrived: {:?}", service.sync().reference);
}

#[tokio::test(flavor = "multi_thread")]
async fn the_reference_data_is_downloaded_and_counted() {
    let root = folder("download");
    let service = start(&root, dofusdb().await).await;
    wait_for_total(&service).await;
    assert!(root.join("config").join("reference.json").exists());
    service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn a_fresh_copy_is_used_without_asking_again() {
    let root = folder("cache");
    let first = start(&root, dofusdb().await).await;
    wait_for_total(&first).await;
    first.shutdown().await;
    // The second start points to nothing: only the saved copy can answer.
    let second = start(&root, "http://127.0.0.1:9".to_owned()).await;
    wait_for_total(&second).await;
    second.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn an_unreachable_dofusdb_leaves_the_counter_at_zero_without_failing() {
    let root = folder("down");
    let service = start(&root, "http://127.0.0.1:9".to_owned()).await;
    tokio::time::sleep(Duration::from_millis(300)).await;
    let reference = service.sync().reference;
    assert_eq!((reference.done, reference.total), (0, 0));
    service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn purging_forgets_the_copy() {
    let root = folder("purge");
    let service = start(&root, dofusdb().await).await;
    wait_for_total(&service).await;
    service.purge().await.unwrap();
    assert!(!root.join("config").join("reference.json").exists());
    assert_eq!(service.sync().reference.done, 0);
    service.shutdown().await;
}
