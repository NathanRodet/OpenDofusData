//! Choosing the network adapters to listen on.

use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};

/// The port of the game server.
pub const GAME_PORT: u16 = 5555;
const LOOPBACK_NAME_MARK: &str = "Loopback";

/// What the agent needs to know about a network adapter.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AdapterInfo {
    /// The name the capture library gives it.
    pub name: String,
    /// Its addresses.
    pub addresses: Vec<IpAddr>,
}

/// The filter that keeps only the game traffic, so the rest never reaches the program.
pub fn capture_filter() -> String {
    format!("tcp port {GAME_PORT}")
}

/// Whether the game traffic can pass through this adapter: it has a real address, and is not the loopback.
pub fn is_capture_candidate(adapter: &AdapterInfo) -> bool {
    !adapter.name.contains(LOOPBACK_NAME_MARK) && adapter.addresses.iter().any(is_routable)
}

fn is_routable(address: &IpAddr) -> bool {
    match address {
        IpAddr::V4(address) => is_routable_v4(address),
        IpAddr::V6(address) => is_routable_v6(address),
    }
}

fn is_routable_v4(address: &Ipv4Addr) -> bool {
    !(address.is_unspecified() || address.is_loopback() || address.is_link_local())
}

fn is_routable_v6(address: &Ipv6Addr) -> bool {
    let link_local = (address.segments()[0] & 0xffc0) == 0xfe80;
    !(address.is_unspecified() || address.is_loopback() || link_local)
}
