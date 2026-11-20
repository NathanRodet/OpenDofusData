//! The HTTP client of the collector, against a real server running in the test.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::sync::{Arc, Mutex};

use axum::extract::State;
use axum::http::{HeaderMap, StatusCode};
use axum::routing::{get, post};
use axum::{Json, Router};
use odd_core::{Event, HdvLots, Offer, Payload, SCHEMA_VERSION};
use odd_sync::{EventResult, ServerStatus, SyncClient, SyncError};
use serde_json::{Value, json};

const KEY: &str = "odd_test-key";

type Seen = Arc<Mutex<Vec<(HeaderMap, Value)>>>;

fn event(id: &str) -> Event {
    let offer = Offer {
        offer_id: 1,
        price: 100,
        effects: vec![],
        unmapped: vec![],
    };
    Event {
        schema: SCHEMA_VERSION,
        event_id: id.to_owned(),
        observed_at: "2026-11-19T10:00:00Z".to_owned(),
        game_server: "Kourial".to_owned(),
        client_version: "2.4.0".to_owned(),
        payload: Payload::HdvLots(HdvLots::unique(1, Some(11), vec![offer])),
    }
}

async fn serve(app: Router) -> String {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    format!("http://{address}")
}

fn authorised(headers: &HeaderMap) -> bool {
    headers
        .get("authorization")
        .is_some_and(|value| value == format!("Bearer {KEY}").as_str())
}

/// A collector that records what it receives and answers `stored` for every object.
fn recording_collector(seen: Seen) -> Router {
    async fn events(
        State(seen): State<Seen>,
        headers: HeaderMap,
        Json(body): Json<Value>,
    ) -> (StatusCode, Json<Value>) {
        if !authorised(&headers) {
            return (StatusCode::UNAUTHORIZED, Json(json!({})));
        }
        let results: Vec<Value> = body["events"]
            .as_array()
            .unwrap()
            .iter()
            .map(|event| json!({ "event_id": event["event_id"], "status": "stored" }))
            .collect();
        seen.lock().unwrap().push((headers, body));
        (StatusCode::ACCEPTED, Json(json!({ "results": results })))
    }
    async fn check(headers: HeaderMap) -> (StatusCode, Json<Value>) {
        if authorised(&headers) {
            (
                StatusCode::OK,
                Json(json!({ "label": "player", "expires_at": "2026-11-26T00:00:00Z" })),
            )
        } else {
            (StatusCode::UNAUTHORIZED, Json(json!({})))
        }
    }
    Router::new()
        .route("/v1/events", post(events))
        .route("/v1/check", get(check))
        .with_state(seen)
}

fn fixed_answer(status: StatusCode) -> Router {
    Router::new()
        .route("/v1/events", post(move || async move { status }))
        .route("/v1/check", get(move || async move { status }))
}

#[tokio::test]
async fn the_key_check_returns_who_the_key_is_for_and_when_it_expires() {
    let url = serve(recording_collector(Seen::default())).await;
    let info = SyncClient::new(&url, KEY).unwrap().check().await.unwrap();
    assert_eq!(
        (info.label.as_str(), info.expires_at.as_str()),
        ("player", "2026-11-26T00:00:00Z")
    );
}

#[tokio::test]
async fn a_wrong_key_is_refused() {
    let url = serve(recording_collector(Seen::default())).await;
    let client = SyncClient::new(&url, "odd_other").unwrap();
    assert!(matches!(client.check().await, Err(SyncError::KeyRefused)));
    assert!(matches!(client.send(&[event("a")]).await, Err(SyncError::KeyRefused)));
}

#[tokio::test]
async fn a_batch_is_posted_with_the_key_and_every_result_is_read() {
    let seen = Seen::default();
    let url = serve(recording_collector(seen.clone())).await;
    let results = SyncClient::new(&url, KEY)
        .unwrap()
        .send(&[event("a"), event("b")])
        .await
        .unwrap();
    assert_eq!(
        results,
        [
            EventResult {
                event_id: "a".to_owned(),
                status: ServerStatus::Stored
            },
            EventResult {
                event_id: "b".to_owned(),
                status: ServerStatus::Stored
            },
        ]
    );
    let seen = seen.lock().unwrap();
    let (headers, body) = &seen[0];
    assert_eq!(body["events"].as_array().unwrap().len(), 2);
    assert_eq!(headers["content-type"], "application/json");
}

#[tokio::test]
async fn the_client_does_not_tell_more_than_its_name_and_version() {
    let seen = Seen::default();
    let url = serve(recording_collector(seen.clone())).await;
    SyncClient::new(&url, KEY).unwrap().send(&[event("a")]).await.unwrap();
    let agent = seen.lock().unwrap()[0].0["user-agent"].to_str().unwrap().to_owned();
    assert!(agent.starts_with("open-dofus-data/") && !agent.contains(' '), "{agent}");
}

#[tokio::test]
async fn a_trailing_slash_in_the_address_is_fine() {
    let url = serve(recording_collector(Seen::default())).await;
    assert!(SyncClient::new(&format!("{url}/"), KEY).unwrap().check().await.is_ok());
}

#[tokio::test]
async fn server_errors_can_be_retried() {
    let url = serve(fixed_answer(StatusCode::SERVICE_UNAVAILABLE)).await;
    let client = SyncClient::new(&url, KEY).unwrap();
    assert!(matches!(
        client.send(&[event("a")]).await,
        Err(SyncError::Unavailable(_))
    ));
    assert!(matches!(client.check().await, Err(SyncError::Unavailable(_))));
}

#[tokio::test]
async fn a_refusal_of_the_batch_is_not_worth_retrying() {
    for status in [
        StatusCode::PAYLOAD_TOO_LARGE,
        StatusCode::UNPROCESSABLE_ENTITY,
        StatusCode::BAD_REQUEST,
    ] {
        let url = serve(fixed_answer(status)).await;
        let result = SyncClient::new(&url, KEY).unwrap().send(&[event("a")]).await;
        assert!(
            matches!(result, Err(SyncError::Refused { status: code }) if code == status.as_u16()),
            "{result:?}"
        );
    }
}

#[tokio::test]
async fn an_unreachable_server_can_be_retried() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    drop(listener);
    let result = SyncClient::new(&url, KEY).unwrap().send(&[event("a")]).await;
    assert!(matches!(result, Err(SyncError::Unavailable(_))), "{result:?}");
}

#[test]
fn an_address_that_is_not_http_is_refused() {
    for url in ["", "not a url", "ftp://example.org", "example.org"] {
        assert!(
            matches!(SyncClient::new(url, KEY), Err(SyncError::InvalidAddress)),
            "{url}"
        );
    }
}
