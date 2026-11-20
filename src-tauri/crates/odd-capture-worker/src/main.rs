//! The capture worker: the only program linked to Npcap.
//!
//! It listens on every adapter that can carry the game traffic and writes each captured frame on its output
//! (a length, then the frame, see `odd-capture`). It stops when its input closes, that is when the agent ends.
//! Messages for the agent go to the error output and never contain an address.
#![forbid(unsafe_code)]

mod adapter;

use std::io::{self, Read};
use std::process::ExitCode;
use std::sync::{Arc, Mutex};
use std::thread;

use odd_capture::is_capture_candidate;
use pcap::Device;

const EXIT_NPCAP_UNAVAILABLE: u8 = 2;
const EXIT_NO_ADAPTER: u8 = 3;

type SharedOutput = Arc<Mutex<io::Stdout>>;

fn main() -> ExitCode {
    let devices = match Device::list() {
        Ok(devices) => devices,
        Err(error) => {
            eprintln!("Npcap is not usable: {error}");
            return ExitCode::from(EXIT_NPCAP_UNAVAILABLE);
        }
    };
    let candidates: Vec<Device> = devices
        .into_iter()
        .filter(|device| is_capture_candidate(&adapter::info_of(device)))
        .collect();
    if candidates.is_empty() {
        eprintln!("no network adapter can carry the game traffic");
        return ExitCode::from(EXIT_NO_ADAPTER);
    }
    let output: SharedOutput = Arc::new(Mutex::new(io::stdout()));
    for device in candidates {
        let output = Arc::clone(&output);
        thread::spawn(move || adapter::capture(device, &output));
    }
    wait_for_the_agent_to_end();
    ExitCode::SUCCESS
}

/// Blocks until the agent closes the input of the worker (or dies).
fn wait_for_the_agent_to_end() {
    let mut sink = [0_u8; 64];
    let mut input = io::stdin();
    while matches!(input.read(&mut sink), Ok(count) if count > 0) {}
}
