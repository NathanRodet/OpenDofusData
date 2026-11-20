//! The updater against a fake GitHub: release listing, checksum file and installer download.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use axum::Router;
use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::get;
use odd_update::{UpdateError, Updater};
use serde_json::json;
use sha2::{Digest, Sha256};

const INSTALLER: &[u8] = b"pretend this is an installer, long enough to arrive in several pieces";

struct Fake {
    tag: String,
    installer: Vec<u8>,
    checksum: Option<String>,
    status: StatusCode,
    asset_origin: Option<String>,
}

type Shared = Arc<Mutex<Fake>>;

fn hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes).iter().map(|byte| format!("{byte:02x}")).collect()
}

fn fake(tag: &str) -> Shared {
    Arc::new(Mutex::new(Fake {
        tag: tag.to_owned(),
        installer: INSTALLER.to_vec(),
        checksum: Some(format!("{}  open-dofus-data_v2.5.0_setup.exe\n", hex(INSTALLER))),
        status: StatusCode::OK,
        asset_origin: None,
    }))
}

async fn serve(shared: Shared) -> String {
    async fn release(State(shared): State<Shared>, headers: axum::http::HeaderMap) -> (StatusCode, String) {
        let host = headers.get("host").unwrap().to_str().unwrap().to_owned();
        let fake = shared.lock().unwrap();
        let origin = fake.asset_origin.clone().unwrap_or_else(|| format!("http://{host}"));
        let version = fake.tag.trim_start_matches('v').to_owned();
        let name = format!("open-dofus-data_v{version}_setup.exe");
        let mut assets = vec![
            json!({ "name": name, "browser_download_url": format!("{origin}/file/{name}"), "size": fake.installer.len() }),
        ];
        if fake.checksum.is_some() {
            assets.push(json!({ "name": format!("{name}.sha256"), "browser_download_url": format!("{origin}/file/{name}.sha256"), "size": 90 }));
        }
        (
            fake.status,
            json!({ "tag_name": fake.tag, "assets": assets }).to_string(),
        )
    }
    async fn file(State(shared): State<Shared>, axum::extract::Path(name): axum::extract::Path<String>) -> Vec<u8> {
        let fake = shared.lock().unwrap();
        if name.ends_with(".sha256") {
            fake.checksum.clone().unwrap_or_default().into_bytes()
        } else {
            fake.installer.clone()
        }
    }
    let app = Router::new()
        .route("/latest", get(release))
        .route("/file/{name}", get(file))
        .with_state(shared);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    url
}

fn folder(name: &str) -> PathBuf {
    let path = std::env::temp_dir().join(format!("odd-update-test-{}-{name}", std::process::id()));
    let _ = std::fs::remove_dir_all(&path);
    std::fs::create_dir_all(&path).unwrap();
    path
}

async fn updater(shared: Shared, current: &str) -> Updater {
    let url = serve(shared).await;
    Updater::new(&format!("{url}/latest"), current).unwrap()
}

#[tokio::test]
async fn a_newer_release_is_offered_with_its_checksum() {
    let release = updater(fake("v2.5.0"), "2.4.0").await.latest().await.unwrap().unwrap();
    assert_eq!(release.version, "2.5.0");
    assert_eq!(release.file_name, "open-dofus-data_v2.5.0_setup.exe");
    assert_eq!(release.sha256, hex(INSTALLER));
    assert_eq!(release.size, Some(INSTALLER.len() as u64));
}

#[tokio::test]
async fn the_same_or_an_older_release_offers_nothing() {
    assert!(updater(fake("v2.4.0"), "2.4.0").await.latest().await.unwrap().is_none());
    assert!(updater(fake("v2.3.9"), "2.4.0").await.latest().await.unwrap().is_none());
}

#[tokio::test]
async fn a_release_without_checksum_is_an_error_not_an_update() {
    let shared = fake("v2.5.0");
    shared.lock().unwrap().checksum = None;
    let error = updater(shared, "2.4.0").await.latest().await.unwrap_err();
    assert!(matches!(error, UpdateError::MissingChecksum), "{error:?}");
}

#[tokio::test]
async fn an_unreachable_listing_is_an_error() {
    let shared = fake("v2.5.0");
    shared.lock().unwrap().status = StatusCode::NOT_FOUND;
    assert!(matches!(
        updater(shared, "2.4.0").await.latest().await,
        Err(UpdateError::Unavailable(_))
    ));
}

#[tokio::test]
async fn assets_on_another_insecure_origin_are_refused() {
    let shared = fake("v2.5.0");
    shared.lock().unwrap().asset_origin = Some("http://example.invalid".to_owned());
    let error = updater(shared, "2.4.0").await.latest().await.unwrap_err();
    assert!(matches!(error, UpdateError::UntrustedUrl), "{error:?}");
}

#[tokio::test]
async fn the_installer_is_downloaded_checked_and_reported() {
    let updater = updater(fake("v2.5.0"), "2.4.0").await;
    let release = updater.latest().await.unwrap().unwrap();
    let dir = folder("ok");
    let mut seen = Vec::new();
    let path = updater
        .download(&release, &dir, |done, total| seen.push((done, total)))
        .await
        .unwrap();
    assert_eq!(std::fs::read(&path).unwrap(), INSTALLER);
    assert_eq!(path.file_name().unwrap(), "open-dofus-data_v2.5.0_setup.exe");
    assert_eq!(
        seen.last().copied(),
        Some((INSTALLER.len() as u64, Some(INSTALLER.len() as u64)))
    );
    assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 1, "no temporary file is left");
}

#[tokio::test]
async fn a_corrupted_installer_is_deleted_and_refused() {
    let shared = fake("v2.5.0");
    let updater = updater(Arc::clone(&shared), "2.4.0").await;
    let release = updater.latest().await.unwrap().unwrap();
    shared.lock().unwrap().installer = b"tampered".to_vec();
    let dir = folder("bad");
    let error = updater.download(&release, &dir, |_, _| {}).await.unwrap_err();
    assert!(matches!(error, UpdateError::ChecksumMismatch), "{error:?}");
    assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 0);
}
