//! Which network adapters can carry the game traffic.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::net::IpAddr;

use odd_capture::{AdapterInfo, GAME_PORT, capture_filter, is_capture_candidate};

fn adapter(name: &str, addresses: &[&str]) -> AdapterInfo {
    AdapterInfo {
        name: name.to_owned(),
        addresses: addresses
            .iter()
            .map(|address| address.parse::<IpAddr>().unwrap())
            .collect(),
    }
}

#[test]
fn an_adapter_with_a_private_ipv4_address_is_a_candidate() {
    assert!(is_capture_candidate(&adapter("wifi", &["fe80::1", "192.168.1.20"])));
}

#[test]
fn an_adapter_with_a_public_ipv6_address_is_a_candidate() {
    assert!(is_capture_candidate(&adapter("ethernet", &["2001:db8::7"])));
}

#[test]
fn an_adapter_with_only_link_local_addresses_is_not() {
    assert!(!is_capture_candidate(&adapter(
        "wifi-direct",
        &["169.254.10.2", "fe80::abcd"]
    )));
}

#[test]
fn the_loopback_adapter_is_not() {
    assert!(!is_capture_candidate(&adapter(
        "\\Device\\NPF_Loopback",
        &["127.0.0.1", "192.168.1.20"]
    )));
    assert!(!is_capture_candidate(&adapter("lo", &["127.0.0.1", "::1"])));
}

#[test]
fn an_adapter_without_address_is_not() {
    assert!(!is_capture_candidate(&adapter("down", &[])));
    assert!(!is_capture_candidate(&adapter("unspecified", &["0.0.0.0", "::"])));
}

#[test]
fn the_filter_keeps_only_the_game_port() {
    assert_eq!(capture_filter(), format!("tcp port {GAME_PORT}"));
    assert_eq!(GAME_PORT, 5555);
}
