//! Reading a TCP segment of the game connection out of a raw Ethernet frame.

use std::net::{IpAddr, SocketAddr};

use etherparse::{NetSlice, SlicedPacket, TcpSlice, TransportSlice};

use crate::flow::{FlowKey, Side, TcpSegment};

/// Reads an Ethernet frame. Returns `None` for anything that is not TCP to or from `server_port`.
pub fn parse_ethernet_frame(frame: &[u8], server_port: u16) -> Option<TcpSegment> {
    let packet = SlicedPacket::from_ethernet(frame).ok()?;
    let Some(TransportSlice::Tcp(tcp)) = &packet.transport else {
        return None;
    };
    let from = side_of(tcp, server_port)?;
    let (source, destination) = addresses(packet.net.as_ref()?)?;
    let (client, server) = match from {
        Side::Client => (
            SocketAddr::new(source, tcp.source_port()),
            SocketAddr::new(destination, tcp.destination_port()),
        ),
        Side::Server => (
            SocketAddr::new(destination, tcp.destination_port()),
            SocketAddr::new(source, tcp.source_port()),
        ),
    };
    Some(TcpSegment {
        key: FlowKey::new(client, server),
        from,
        seq: tcp.sequence_number(),
        payload: tcp.payload().to_vec(),
        syn: tcp.syn(),
        fin: tcp.fin(),
        rst: tcp.rst(),
    })
}

fn side_of(tcp: &TcpSlice<'_>, server_port: u16) -> Option<Side> {
    if tcp.destination_port() == server_port {
        Some(Side::Client)
    } else if tcp.source_port() == server_port {
        Some(Side::Server)
    } else {
        None
    }
}

fn addresses(net: &NetSlice<'_>) -> Option<(IpAddr, IpAddr)> {
    match net {
        NetSlice::Ipv4(ip) => {
            let header = ip.header();
            Some((header.source_addr().into(), header.destination_addr().into()))
        }
        NetSlice::Ipv6(ip) => {
            let header = ip.header();
            Some((header.source_addr().into(), header.destination_addr().into()))
        }
        NetSlice::Arp(_) => None,
    }
}
