//! Looking for an update and downloading it, against a fake GitHub.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::path::PathBuf;
use std::sync::Arc;

use axum::Router;
use axum::extract::Path as UrlPath;
use axum::http::HeaderMap;
use axum::routing::get;
use odd_capture::FrameSource;
use odd_service::{NpcapState, Service, ServiceConfig, ServiceError, SourceError, SourceFactory};
use serde_json::json;
use sha2::{Digest, Sha256};

const INSTALLER: &[u8] = b"an installer";
const NAME: &str = "open-dofus-data_v2.5.0_setup.exe";

struct NoCapture;

impl SourceFactory for NoCapture {
    fn npcap(&self) -> NpcapState {
        NpcapState::Missing
    }

    fn open(&self) -> Result<Box<dyn FrameSource>, SourceError> {
        Err(SourceError::NpcapMissing)
    }
}

async fn github(tag: &'static str) -> String {
    async fn file(UrlPath(name): UrlPath<String>) -> Vec<u8> {
        if name.ends_with(".sha256") {
            let hash: String = Sha256::digest(INSTALLER)
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect();
            format!("{hash}  {NAME}\n").into_bytes()
        } else {
            INSTALLER.to_vec()
        }
    }
    let listing = move |headers: HeaderMap| async move {
        let origin = format!("http://{}", headers.get("host").unwrap().to_str().unwrap());
        json!({ "tag_name": tag, "assets": [
            { "name": NAME, "browser_download_url": format!("{origin}/file/{NAME}"), "size": INSTALLER.len() },
            { "name": format!("{NAME}.sha256"), "browser_download_url": format!("{origin}/file/{NAME}.sha256"), "size": 90 },
        ] })
        .to_string()
    };
    let app = Router::new()
        .route("/latest", get(listing))
        .route("/file/{name}", get(file));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}/latest", listener.local_addr().unwrap());
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    url
}

fn folder(name: &str) -> PathBuf {
    let path = std::env::temp_dir().join(format!("odd-service-update-{}-{name}", std::process::id()));
    let _ = std::fs::remove_dir_all(&path);
    path
}

async fn start(name: &str, releases_url: String) -> (Service, PathBuf) {
    let root = folder(name);
    let config = ServiceConfig {
        config_dir: root.join("config"),
        download_dir: root.join("downloads"),
        app_version: "2.4.0".to_owned(),
        releases_url,
        reference_url: "http://127.0.0.1:9".to_owned(),
    };
    let service = Service::start(
        config,
        tokio::runtime::Handle::current(),
        Arc::new(NoCapture),
        Arc::new(|_| {}),
    )
    .await;
    (service, root)
}

#[tokio::test(flavor = "multi_thread")]
async fn nothing_is_offered_before_looking() {
    let (service, _) = start("none", github("v2.5.0").await).await;
    assert!(service.status().update.is_none());
    service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn a_newer_release_shows_in_the_status() {
    let (service, _) = start("newer", github("v2.5.0").await).await;
    let offered = service.check_update().await.unwrap().unwrap();
    assert_eq!((offered.version.as_str(), offered.file_name.as_str()), ("2.5.0", NAME));
    assert_eq!(service.status().update, Some(offered));
    service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn an_up_to_date_application_offers_nothing() {
    let (service, _) = start("current", github("v2.4.0").await).await;
    assert!(service.check_update().await.unwrap().is_none());
    assert!(service.status().update.is_none());
    service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn the_download_returns_the_checked_installer_and_shows_the_end() {
    let (service, root) = start("download", github("v2.5.0").await).await;
    service.check_update().await.unwrap();
    let installer = service.start_update().await.unwrap();
    assert_eq!(installer, root.join("downloads").join(NAME));
    assert_eq!(std::fs::read(&installer).unwrap(), INSTALLER);
    let shown = service.status().update.unwrap();
    assert_eq!((shown.progress, shown.downloaded_mb.is_some()), (Some(100), true));
    service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn downloading_without_an_offer_is_an_error() {
    let (service, _) = start("no-offer", github("v2.5.0").await).await;
    assert!(matches!(service.start_update().await, Err(ServiceError::NoUpdate)));
    service.shutdown().await;
}

#[tokio::test(flavor = "multi_thread")]
async fn an_unreachable_github_is_an_error_not_a_crash() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}/latest", listener.local_addr().unwrap());
    drop(listener);
    let (service, _) = start("down", url).await;
    assert!(matches!(service.check_update().await, Err(ServiceError::Update(_))));
    service.shutdown().await;
}
