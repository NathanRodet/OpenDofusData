//! The agent from frames to the collector, with real captures, a fake collector and no Npcap.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

mod common;

use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::post;
use axum::{Json, Router};
use common::{Segment, records, segments};
use odd_agent::{Agent, AgentConfig, LogCategory, LogLine, LogSink, LogStatus};
use odd_capture::{FrameSource, Stopper, WorkerError};
use serde_json::{Value, json};

const KEY: &str = "odd_test-key";

struct FrameQueue(VecDeque<Vec<u8>>);

impl FrameSource for FrameQueue {
    fn next_frame(&mut self) -> Result<Option<Vec<u8>>, WorkerError> {
        Ok(self.0.pop_front())
    }
}

/// A source that gives nothing until it is stopped.
struct Silent {
    gate: mpsc::Receiver<()>,
    open: mpsc::Sender<()>,
}

impl FrameSource for Silent {
    fn next_frame(&mut self) -> Result<Option<Vec<u8>>, WorkerError> {
        let _ = self.gate.recv();
        Ok(None)
    }

    fn stopper(&self) -> Stopper {
        let open = self.open.clone();
        Arc::new(move || {
            let _ = open.send(());
        })
    }
}

#[derive(Clone)]
struct Collector {
    received: Arc<Mutex<Vec<Value>>>,
    status: StatusCode,
}

async fn handle(State(collector): State<Collector>, Json(body): Json<Value>) -> (StatusCode, Json<Value>) {
    if collector.status != StatusCode::ACCEPTED {
        return (collector.status, Json(json!({})));
    }
    let events = body["events"].as_array().unwrap();
    collector.received.lock().unwrap().extend(events.iter().cloned());
    let results: Vec<Value> = events
        .iter()
        .map(|e| json!({ "event_id": e["event_id"], "status": "stored" }))
        .collect();
    (StatusCode::ACCEPTED, Json(json!({ "results": results })))
}

async fn collector(status: StatusCode) -> (String, Collector) {
    let state = Collector {
        received: Arc::default(),
        status,
    };
    let app = Router::new()
        .route("/v1/events", post(handle))
        .with_state(state.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    (url, state)
}

fn sink() -> (LogSink, Arc<Mutex<Vec<LogLine>>>) {
    let lines: Arc<Mutex<Vec<LogLine>>> = Arc::default();
    let seen = Arc::clone(&lines);
    (Arc::new(move |line| seen.lock().unwrap().push(line)), lines)
}

fn config(url: &str, key: &str) -> AgentConfig {
    AgentConfig {
        server_url: url.to_owned(),
        api_key: key.to_owned(),
        game_server: "Kourial".to_owned(),
        client_version: "2.4.0".to_owned(),
    }
}

fn frames_of(name: &str) -> FrameQueue {
    FrameQueue(
        segments(&records(name), 1460, 50_000)
            .iter()
            .map(Segment::frame)
            .collect(),
    )
}

async fn wait_until(what: &str, condition: impl Fn() -> bool) {
    for _ in 0..400 {
        if condition() {
            return;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    panic!("timeout waiting for: {what}");
}

#[tokio::test(flavor = "multi_thread")]
async fn a_replayed_session_reaches_the_collector_as_objects_with_unique_ids() {
    let (url, collector) = collector(StatusCode::ACCEPTED).await;
    let (sink, lines) = sink();
    let handle = tokio::runtime::Handle::current();
    let agent = Agent::start(config(&url, KEY), Box::new(frames_of("brisage-multi")), &handle, sink).unwrap();
    wait_until("objects stored", || agent.snapshot().stored >= 2).await;
    let received = collector.received.lock().unwrap().clone();
    assert!(received.len() >= 2);
    let ids: HashSet<&str> = received.iter().map(|e| e["event_id"].as_str().unwrap()).collect();
    assert_eq!(ids.len(), received.len(), "every object has its own id");
    assert!(
        received
            .iter()
            .all(|e| e["game_server"] == "Kourial" && e["client_version"] == "2.4.0")
    );
    assert!(
        received
            .iter()
            .all(|e| e["observed_at"].as_str().unwrap().ends_with('Z'))
    );
    let lines = lines.lock().unwrap().clone();
    let delivered: Vec<&LogLine> = lines.iter().filter(|line| line.note.starts_with("Envoyé")).collect();
    assert!(delivered.len() >= 2 && delivered.iter().all(|line| line.category == Some(LogCategory::Brisage)));
    assert!(
        delivered
            .iter()
            .all(|line| line.status == LogStatus::Analyzed && line.payload.is_some())
    );
    agent.stop().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn without_a_key_nothing_is_sent_and_the_logs_say_so() {
    let (url, collector) = collector(StatusCode::ACCEPTED).await;
    let (sink, lines) = sink();
    let handle = tokio::runtime::Handle::current();
    let agent = Agent::start(config(&url, ""), Box::new(frames_of("hdv-ressource")), &handle, sink).unwrap();
    wait_until("the object is logged", || !lines.lock().unwrap().is_empty()).await;
    tokio::time::sleep(Duration::from_millis(300)).await;
    assert!(collector.received.lock().unwrap().is_empty());
    let line = lines.lock().unwrap()[0].clone();
    assert_eq!(
        (line.category, line.status),
        (Some(LogCategory::Hdv), LogStatus::Analyzed)
    );
    assert!(line.note.starts_with("Non envoyé"), "{}", line.note);
    agent.stop().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn a_refused_key_is_reported_in_the_logs_and_the_counters() {
    let (url, _collector) = collector(StatusCode::UNAUTHORIZED).await;
    let (sink, lines) = sink();
    let handle = tokio::runtime::Handle::current();
    let agent = Agent::start(config(&url, KEY), Box::new(frames_of("hdv-ressource")), &handle, sink).unwrap();
    wait_until("key refused", || agent.snapshot().key_refused).await;
    let lines = lines.lock().unwrap().clone();
    assert!(
        lines
            .iter()
            .any(|line| line.status == LogStatus::Error && line.summary == "Clé refusée par le serveur")
    );
    agent.stop().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn a_wrong_server_address_is_refused_at_start() {
    let (sink, _lines) = sink();
    let handle = tokio::runtime::Handle::current();
    let source = Box::new(FrameQueue(VecDeque::new()));
    assert!(Agent::start(config("not an address", KEY), source, &handle, sink).is_err());
}

#[tokio::test(flavor = "multi_thread")]
async fn stopping_unblocks_a_source_that_waits_for_frames() {
    let (open, gate) = mpsc::channel();
    let (sink, _lines) = sink();
    let handle = tokio::runtime::Handle::current();
    let agent = Agent::start(
        config("http://127.0.0.1:1", ""),
        Box::new(Silent { gate, open }),
        &handle,
        sink,
    )
    .unwrap();
    tokio::time::timeout(Duration::from_secs(3), agent.stop())
        .await
        .expect("the agent stops");
}

#[tokio::test(flavor = "multi_thread")]
async fn the_end_of_the_capture_is_noted_in_the_logs() {
    let (sink, lines) = sink();
    let handle = tokio::runtime::Handle::current();
    let agent = Agent::start(
        config("http://127.0.0.1:1", ""),
        Box::new(FrameQueue(VecDeque::new())),
        &handle,
        sink,
    )
    .unwrap();
    wait_until("the end is logged", || !lines.lock().unwrap().is_empty()).await;
    let line = lines.lock().unwrap()[0].clone();
    assert_eq!((line.category, line.status), (None, LogStatus::Error));
    assert_eq!(line.summary, "La capture s'est arrêtée");
    agent.stop().await;
}

#[test]
fn log_lines_never_use_a_dash_look_alike_or_a_middle_dot() {
    let texts = [
        "Envoyé au serveur",
        "Non envoyé: aucune clé enregistrée",
        "Clé refusée par le serveur",
    ];
    let counts: HashMap<bool, usize> = texts.iter().fold(HashMap::new(), |mut map, text| {
        *map.entry(text.contains(['\u{2013}', '\u{2014}', '\u{00B7}']))
            .or_default() += 1;
        map
    });
    assert_eq!(counts.get(&true), None);
}
