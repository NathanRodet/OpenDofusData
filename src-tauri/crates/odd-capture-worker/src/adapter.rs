//! Listening on one adapter.

use std::io::Write;
use std::process;

use odd_capture::{AdapterInfo, capture_filter, encode_frame};
use pcap::{Active, Capture, Device, Linktype};

use crate::SharedOutput;

const SNAPLEN: i32 = 65_535;
const READ_TIMEOUT_MS: i32 = 200;

/// What `odd-capture` needs to know about a device.
pub fn info_of(device: &Device) -> AdapterInfo {
    AdapterInfo {
        name: device.name.clone(),
        addresses: device.addresses.iter().map(|address| address.addr).collect(),
    }
}

/// Listens on `device` and writes every game frame on `output`, until the capture fails.
pub fn capture(device: Device, output: &SharedOutput) {
    let name = device.name.clone();
    let mut capture = match open(device) {
        Ok(capture) => capture,
        Err(message) => return eprintln!("adapter {name}: {message}"),
    };
    eprintln!("adapter {name}: listening");
    loop {
        match capture.next_packet() {
            Ok(packet) => write_frame(output, packet.data),
            Err(pcap::Error::TimeoutExpired) => {}
            Err(error) => return eprintln!("adapter {name}: capture stopped: {error}"),
        }
    }
}

fn open(device: Device) -> Result<Capture<Active>, String> {
    let mut capture = Capture::from_device(device)
        .and_then(|inactive| {
            inactive
                .promisc(false)
                .snaplen(SNAPLEN)
                .immediate_mode(true)
                .timeout(READ_TIMEOUT_MS)
                .open()
        })
        .map_err(|error| error.to_string())?;
    if capture.get_datalink() != Linktype::ETHERNET {
        return Err("not an Ethernet adapter, ignored".to_owned());
    }
    capture
        .filter(&capture_filter(), true)
        .map_err(|error| error.to_string())?;
    Ok(capture)
}

/// Writes one frame. If the output is gone the agent is gone too: the worker ends.
fn write_frame(output: &SharedOutput, frame: &[u8]) {
    let Ok(mut stream) = output.lock() else {
        process::exit(1);
    };
    if stream
        .write_all(&encode_frame(frame))
        .and_then(|()| stream.flush())
        .is_err()
    {
        process::exit(0);
    }
}
