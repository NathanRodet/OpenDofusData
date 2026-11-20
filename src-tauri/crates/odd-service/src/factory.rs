//! Where the captured frames come from: the capture worker in production, anything in tests.

use std::path::PathBuf;

use odd_capture::{FrameSource, WorkerProcess, find_npcap_directory, npcap_candidates, worker_command};

use crate::dto::NpcapState;

/// Why the capture could not start.
#[derive(Debug, thiserror::Error)]
pub enum SourceError {
    /// Npcap is not installed.
    #[error("Npcap is not installed")]
    NpcapMissing,
    /// The capture program is not next to the application.
    #[error("the capture program is missing")]
    WorkerMissing,
    /// The capture program could not be started.
    #[error("the capture program could not start: {0}")]
    Start(String),
}

/// Opens the source of frames.
pub trait SourceFactory: Send + Sync {
    /// Whether the capture can start.
    fn npcap(&self) -> NpcapState;

    /// Opens a new source.
    fn open(&self) -> Result<Box<dyn FrameSource>, SourceError>;
}

/// Starts the capture worker found next to the application.
#[derive(Debug, Clone)]
pub struct WorkerFactory {
    worker: PathBuf,
    candidates: Vec<PathBuf>,
}

impl WorkerFactory {
    /// A factory for the worker at `worker`, looking for Npcap where it installs itself.
    pub fn new(worker: PathBuf) -> Self {
        Self {
            worker,
            candidates: npcap_candidates(),
        }
    }
}

impl SourceFactory for WorkerFactory {
    fn npcap(&self) -> NpcapState {
        if self.worker.is_file() && find_npcap_directory(&self.candidates).is_some() {
            NpcapState::Ok
        } else {
            NpcapState::Missing
        }
    }

    fn open(&self) -> Result<Box<dyn FrameSource>, SourceError> {
        let directory = find_npcap_directory(&self.candidates).ok_or(SourceError::NpcapMissing)?;
        if !self.worker.is_file() {
            return Err(SourceError::WorkerMissing);
        }
        let command =
            worker_command(&self.worker, Some(&directory)).map_err(|error| SourceError::Start(error.to_string()))?;
        let process = WorkerProcess::spawn(command).map_err(|error| SourceError::Start(error.to_string()))?;
        Ok(Box::new(process))
    }
}
