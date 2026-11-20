//! The service behind the interface, with a fake collector and a fake capture.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use axum::Json;
use axum::Router;
use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::{get, post};
use odd_capture::{FrameSource, Stopper, WorkerError};
use odd_service::{
    ConnectionKind, KeyState, LogEntry, NpcapState, Service, ServiceConfig, Settings, SourceError, SourceFactory,
};
use serde_json::{Value, json};
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

/// What the fake collector answers to the key check.
type CheckAnswer = Arc<Mutex<(StatusCode, String)>>;

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

struct Factory {
    npcap_missing: bool,
}

impl SourceFactory for Factory {
    fn npcap(&self) -> NpcapState {
        if self.npcap_missing {
            NpcapState::Missing
        } else {
            NpcapState::Ok
        }
    }

    fn open(&self) -> Result<Box<dyn FrameSource>, SourceError> {
        if self.npcap_missing {
            return Err(SourceError::NpcapMissing);
        }
        let (open, gate) = mpsc::channel();
        Ok(Box::new(Silent { gate, open }))
    }
}

fn days_from_now(days: i64) -> String {
    (OffsetDateTime::now_utc() + time::Duration::days(days))
        .format(&Rfc3339)
        .unwrap()
}

async fn collector(answer: CheckAnswer) -> String {
    async fn check(State(answer): State<CheckAnswer>) -> (StatusCode, Json<Value>) {
        let (status, expires_at) = answer.lock().unwrap().clone();
        (status, Json(json!({ "label": "player", "expires_at": expires_at })))
    }
    async fn events() -> (StatusCode, Json<Value>) {
        (StatusCode::ACCEPTED, Json(json!({ "results": [] })))
    }
    let app = Router::new()
        .route("/v1/check", get(check))
        .route("/v1/events", post(events))
        .with_state(answer);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    url
}

fn folder(name: &str) -> PathBuf {
    let path = std::env::temp_dir().join(format!("odd-service-test-{}-{name}", std::process::id()));
    let _ = std::fs::remove_dir_all(&path);
    path
}

struct Running {
    service: Service,
    emitted: Arc<Mutex<Vec<LogEntry>>>,
    directory: PathBuf,
}

async fn start_in(directory: &Path, npcap_missing: bool) -> (Service, Arc<Mutex<Vec<LogEntry>>>) {
    let emitted: Arc<Mutex<Vec<LogEntry>>> = Arc::default();
    let seen = Arc::clone(&emitted);
    let config = ServiceConfig {
        config_dir: directory.to_path_buf(),
        download_dir: directory.join("downloads"),
        releases_url: "http://127.0.0.1:9/latest".to_owned(),
        reference_url: "http://127.0.0.1:9".to_owned(),
        app_version: "2.4.0".to_owned(),
    };
    let service = Service::start(
        config,
        tokio::runtime::Handle::current(),
        Arc::new(Factory { npcap_missing }),
        Arc::new(move |entry| seen.lock().unwrap().push(entry)),
    )
    .await;
    (service, emitted)
}

async fn start(name: &str, settings: Option<Settings>, npcap_missing: bool) -> Running {
    let directory = folder(name);
    if let Some(settings) = settings {
        odd_service::SettingsStore::new(directory.clone())
            .save(&settings)
            .unwrap();
    }
    let (service, emitted) = start_in(&directory, npcap_missing).await;
    Running {
        service,
        emitted,
        directory,
    }
}

fn player(url: &str, key: &str) -> Settings {
    Settings {
        server_url: url.to_owned(),
        game_server: "Kourial".to_owned(),
        api_key: key.to_owned(),
        logs_enabled: true,
    }
}

async fn wait_until(what: &str, condition: impl Fn() -> bool) {
    for _ in 0..600 {
        if condition() {
            return;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    panic!("timeout waiting for: {what}");
}

fn valid_answer(days: i64) -> CheckAnswer {
    Arc::new(Mutex::new((StatusCode::OK, days_from_now(days))))
}

#[tokio::test(flavor = "multi_thread")]
async fn without_a_key_the_status_says_so() {
    let running = start("no-key", None, false).await;
    let status = running.service.status();
    assert_eq!(
        (status.key, status.npcap, status.connection),
        (KeyState::Missing, NpcapState::Ok, ConnectionKind::Offline)
    );
    assert_eq!(status.app_version, "2.4.0");
    assert!(status.update.is_none() && status.key_expires_in_days.is_none());
    let sync = running.service.sync();
    assert_eq!((sync.sent.done, sync.sent.pending, sync.sent.errors), (0, 0, 0));
    running.service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn a_valid_key_shows_the_days_left_and_the_connection() {
    let url = collector(valid_answer(5)).await;
    let running = start("valid", Some(player(&url, "odd_ok")), false).await;
    wait_until("connected", || {
        running.service.status().connection == ConnectionKind::Connected
    })
    .await;
    let status = running.service.status();
    assert_eq!(status.key, KeyState::Valid);
    assert!(
        matches!(status.key_expires_in_days, Some(4 | 5)),
        "{:?}",
        status.key_expires_in_days
    );
    assert!(status.latency_ms.is_some());
    running.service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn a_key_the_server_refuses_is_refused() {
    let url = collector(Arc::new(Mutex::new((StatusCode::UNAUTHORIZED, String::new())))).await;
    let running = start("refused", Some(player(&url, "odd_bad")), false).await;
    wait_until("refused", || running.service.status().key == KeyState::Refused).await;
    running.service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn a_key_whose_date_has_passed_is_expired() {
    let url = collector(valid_answer(-1)).await;
    let running = start("expired", Some(player(&url, "odd_old")), false).await;
    wait_until("expired", || running.service.status().key == KeyState::Expired).await;
    running.service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn an_unreachable_server_shows_offline() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    drop(listener);
    let running = start("offline", Some(player(&url, "odd_ok")), false).await;
    // Windows takes about two seconds to give up on a closed port.
    wait_until("offline", || {
        running.service.status().connection == ConnectionKind::Offline
    })
    .await;
    running.service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn a_missing_npcap_is_reported_in_the_status_and_the_logs() {
    let running = start("npcap", None, true).await;
    assert_eq!(running.service.status().npcap, NpcapState::Missing);
    let emitted = running.emitted.lock().unwrap().clone();
    assert!(
        emitted.iter().any(|entry| entry.summary == "Npcap est introuvable"),
        "{emitted:?}"
    );
    assert!(emitted.windows(2).all(|pair| pair[0].id < pair[1].id), "ids grow");
    running.service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn the_connection_test_explains_what_happened() {
    let url = collector(valid_answer(3)).await;
    let running = start("test-ok", None, false).await;
    let ok = running.service.test_connection(player(&url, "odd_ok")).await;
    assert!(ok.ok && ok.message.contains("Connexion réussie"), "{}", ok.message);
    let none = running.service.test_connection(player(&url, "")).await;
    assert!(!none.ok && none.message.contains("clé"), "{}", none.message);
    let bad = running
        .service
        .test_connection(player("not an address ::", "odd_ok"))
        .await;
    assert!(!bad.ok && bad.message.contains("adresse"), "{}", bad.message);
    let refused_url = collector(Arc::new(Mutex::new((StatusCode::UNAUTHORIZED, String::new())))).await;
    let refused = running.service.test_connection(player(&refused_url, "odd_bad")).await;
    assert!(!refused.ok && refused.message.contains("refuse"), "{}", refused.message);
    running.service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn saved_settings_apply_at_once_and_survive_a_restart() {
    let url = collector(valid_answer(5)).await;
    let running = start("save", None, false).await;
    running.service.save_settings(player(&url, "odd_new")).await.unwrap();
    wait_until("the new key is checked", || {
        running.service.status().key == KeyState::Valid
    })
    .await;
    assert_eq!(running.service.settings().api_key, "odd_new");
    running.service.shutdown().await;
    let (again, _) = start_in(&running.directory, false).await;
    assert_eq!(again.settings(), player(&url, "odd_new"));
    again.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn purging_forgets_the_settings() {
    let url = collector(valid_answer(5)).await;
    let running = start("purge", Some(player(&url, "odd_ok")), false).await;
    running.service.purge().await.unwrap();
    assert_eq!(running.service.settings(), Settings::default());
    assert_eq!(running.service.status().key, KeyState::Missing);
    assert!(!running.directory.join("settings.json").exists());
    running.service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn the_logs_are_saved_in_a_file_of_the_chosen_folder() {
    let running = start("logs", None, true).await;
    let entries = running.emitted.lock().unwrap().clone();
    let target = folder("logs-out");
    let file = running.service.save_logs(&entries, &target).unwrap();
    assert!(file.starts_with(&target) && file.extension().is_some_and(|extension| extension == "json"));
    let saved: Vec<Value> = serde_json::from_str(&std::fs::read_to_string(file).unwrap()).unwrap();
    assert_eq!(saved.len(), entries.len());
    assert!(saved[0]["payloadNote"].is_string() && saved[0]["summary"].is_string());
    running.service.shutdown().await;
}
