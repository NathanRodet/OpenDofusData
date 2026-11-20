//! The sending loop: batches, retries with a growing delay, freshest object only, key refused.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::post;
use axum::{Json, Router};
use odd_core::{Event, HdvLots, Offer, Payload, SCHEMA_VERSION};
use odd_sync::{Notice, SenderConfig, ServerStatus, SyncClient, SyncStatus, spawn_sender};
use serde_json::{Value, json};

const KEY: &str = "odd_test-key";

/// What the fake collector does, request after request.
#[derive(Clone)]
struct Collector {
    requests: Arc<Mutex<Vec<Vec<String>>>>,
    calls: Arc<AtomicUsize>,
    /// Statuses answered to the first requests; afterwards the collector answers `stored` for everything.
    script: Arc<Vec<StatusCode>>,
    object_status: &'static str,
}

impl Collector {
    fn new(script: Vec<StatusCode>) -> Self {
        Self {
            requests: Arc::default(),
            calls: Arc::default(),
            script: Arc::new(script),
            object_status: "stored",
        }
    }

    fn batches(&self) -> Vec<Vec<String>> {
        self.requests.lock().unwrap().clone()
    }
}

async fn handle(State(collector): State<Collector>, Json(body): Json<Value>) -> (StatusCode, Json<Value>) {
    let call = collector.calls.fetch_add(1, Ordering::SeqCst);
    let ids: Vec<String> = body["events"]
        .as_array()
        .unwrap()
        .iter()
        .map(|e| e["event_id"].as_str().unwrap().to_owned())
        .collect();
    collector.requests.lock().unwrap().push(ids.clone());
    if let Some(status) = collector.script.get(call).filter(|status| **status != StatusCode::OK) {
        return (*status, Json(json!({})));
    }
    let results: Vec<Value> = ids
        .iter()
        .map(|id| json!({ "event_id": id, "status": collector.object_status, "reason": "no reason" }))
        .collect();
    (StatusCode::ACCEPTED, Json(json!({ "results": results })))
}

async fn serve(collector: Collector) -> String {
    let app = Router::new().route("/v1/events", post(handle)).with_state(collector);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    format!("http://{address}")
}

fn event(id: &str, item: i64, at: &str) -> Event {
    let offer = Offer {
        offer_id: 1,
        price: 1,
        effects: vec![],
        unmapped: vec![],
    };
    Event {
        schema: SCHEMA_VERSION,
        event_id: id.to_owned(),
        observed_at: at.to_owned(),
        game_server: "Kourial".to_owned(),
        client_version: "2.4.0".to_owned(),
        payload: Payload::HdvLots(HdvLots::unique(item, Some(11), vec![offer])),
    }
}

fn fast() -> SenderConfig {
    SenderConfig {
        batch_window: Duration::from_millis(80),
        max_batch: 500,
        backoff_start: Duration::from_millis(20),
        backoff_max: Duration::from_millis(80),
    }
}

struct Running {
    sender: odd_sync::Sender,
    status: Arc<SyncStatus>,
    notices: Arc<Mutex<Vec<Notice>>>,
}

async fn start(url: &str) -> Running {
    let status = Arc::new(SyncStatus::default());
    let notices: Arc<Mutex<Vec<Notice>>> = Arc::default();
    let seen = Arc::clone(&notices);
    let observer = Arc::new(move |notice: Notice| seen.lock().unwrap().push(notice));
    let client = SyncClient::new(url, KEY).unwrap();
    let sender = spawn_sender(client, fast(), Arc::clone(&status), observer);
    Running {
        sender,
        status,
        notices,
    }
}

async fn wait_until(what: &str, condition: impl Fn() -> bool) {
    for _ in 0..300 {
        if condition() {
            return;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    panic!("timeout waiting for: {what}");
}

#[tokio::test]
async fn objects_that_come_together_go_in_one_request() {
    let collector = Collector::new(vec![]);
    let running = start(&serve(collector.clone()).await).await;
    for (index, id) in ["a", "b", "c"].into_iter().enumerate() {
        assert!(
            running
                .sender
                .submit(event(id, i64::try_from(index).unwrap(), "2026-11-19T10:00:00Z"))
        );
    }
    wait_until("three objects stored", || running.status.snapshot().stored == 3).await;
    assert_eq!(collector.batches(), [["a", "b", "c"]]);
    let delivered = running
        .notices
        .lock()
        .unwrap()
        .iter()
        .filter(|n| matches!(n, Notice::Delivered { .. }))
        .count();
    assert_eq!(delivered, 3);
}

#[tokio::test]
async fn a_server_that_fails_is_retried_until_it_answers() {
    let collector = Collector::new(vec![StatusCode::SERVICE_UNAVAILABLE, StatusCode::BAD_GATEWAY]);
    let running = start(&serve(collector.clone()).await).await;
    running.sender.submit(event("a", 1, "2026-11-19T10:00:00Z"));
    wait_until("the object stored after the retries", || {
        running.status.snapshot().stored == 1
    })
    .await;
    assert_eq!(collector.batches().len(), 3);
    assert_eq!(running.status.snapshot().failed_attempts, 2);
}

#[tokio::test]
async fn while_the_server_is_down_only_the_freshest_object_of_a_slot_waits() {
    let collector = Collector::new(vec![StatusCode::SERVICE_UNAVAILABLE]);
    let running = start(&serve(collector.clone()).await).await;
    running.sender.submit(event("old", 1, "2026-11-19T10:00:00Z"));
    running.sender.submit(event("new", 1, "2026-11-19T10:05:00Z"));
    wait_until("stored", || running.status.snapshot().stored >= 1).await;
    let delivered: Vec<String> = collector.batches().into_iter().flatten().collect();
    assert_eq!(
        delivered,
        ["new", "new"],
        "the older object was never sent, only the freshest, twice (one failed)"
    );
}

#[tokio::test]
async fn a_refused_key_stops_the_sending() {
    let collector = Collector::new(vec![StatusCode::UNAUTHORIZED]);
    let running = start(&serve(collector.clone()).await).await;
    running.sender.submit(event("a", 1, "2026-11-19T10:00:00Z"));
    wait_until("key refused", || running.status.snapshot().key_refused).await;
    assert!(
        running
            .notices
            .lock()
            .unwrap()
            .iter()
            .any(|n| matches!(n, Notice::KeyRefused))
    );
    tokio::time::sleep(Duration::from_millis(200)).await;
    assert_eq!(collector.batches().len(), 1, "nothing is sent again with a refused key");
}

#[tokio::test]
async fn an_object_the_server_rejects_is_not_sent_again() {
    let mut collector = Collector::new(vec![]);
    collector.object_status = "rejected";
    let running = start(&serve(collector.clone()).await).await;
    running.sender.submit(event("a", 1, "2026-11-19T10:00:00Z"));
    wait_until("rejected", || running.status.snapshot().rejected == 1).await;
    tokio::time::sleep(Duration::from_millis(200)).await;
    assert_eq!(collector.batches().len(), 1);
    let notices = running.notices.lock().unwrap();
    assert!(notices.iter().any(
        |n| matches!(n, Notice::Delivered { status: ServerStatus::Rejected(reason), .. } if reason == "no reason")
    ));
}

#[tokio::test]
async fn an_object_the_server_failed_to_store_is_sent_again() {
    let mut collector = Collector::new(vec![]);
    collector.object_status = "failed";
    let running = start(&serve(collector.clone()).await).await;
    running.sender.submit(event("a", 1, "2026-11-19T10:00:00Z"));
    wait_until("several attempts", || collector.batches().len() >= 3).await;
    assert_eq!(running.status.snapshot().stored, 0);
}

#[tokio::test]
async fn finishing_sends_what_is_still_waiting() {
    let collector = Collector::new(vec![]);
    let running = start(&serve(collector.clone()).await).await;
    running.sender.submit(event("last", 1, "2026-11-19T10:00:00Z"));
    running.sender.finish().await;
    assert_eq!(collector.batches(), [["last"]]);
    assert_eq!(running.status.snapshot().stored, 1);
}
