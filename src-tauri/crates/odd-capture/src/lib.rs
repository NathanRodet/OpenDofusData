//! The capture worker side of the agent: the transport of captured frames, the Npcap lookup and the worker process.
//!
//! The worker is the only program linked to Npcap, so the application starts even where Npcap is missing.
#![forbid(unsafe_code)]

mod adapters;
mod ipc;
mod worker;

pub use adapters::{AdapterInfo, GAME_PORT, capture_filter, is_capture_candidate};
pub use ipc::{FrameReader, IpcError, MAX_FRAME_BYTES, encode_frame};
pub use worker::{
    FrameSource, Stopper, WorkerError, WorkerProcess, find_npcap_directory, npcap_candidates, path_with_npcap,
    worker_command,
};
