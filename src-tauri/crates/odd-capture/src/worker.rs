//! Finding Npcap and running the capture worker, the only program linked to it.

use std::env::{self, JoinPathsError};
use std::ffi::{OsStr, OsString};
use std::io::{self, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdout, Command, Stdio};
use std::sync::{Arc, Mutex};

use crate::ipc::{FrameReader, IpcError};

const NPCAP_LIBRARY: &str = "wpcap.dll";
const DEFAULT_SYSTEM_ROOT: &str = r"C:\Windows";

/// The worker could not be started or read.
#[derive(Debug, thiserror::Error)]
pub enum WorkerError {
    /// The search path cannot be built.
    #[error("cannot build the search path: {0}")]
    Path(#[from] JoinPathsError),
    /// The process cannot be started.
    #[error("cannot start the capture worker: {0}")]
    Start(#[source] io::Error),
    /// The worker's output is not a stream of frames.
    #[error(transparent)]
    Frames(#[from] IpcError),
}

/// Where Npcap puts its libraries: its own folder, or the system folder when installed in WinPcap compatible mode.
pub fn npcap_candidates() -> Vec<PathBuf> {
    let root = env::var_os("SystemRoot").unwrap_or_else(|| OsString::from(DEFAULT_SYSTEM_ROOT));
    let system = PathBuf::from(root).join("System32");
    vec![system.join("Npcap"), system]
}

/// The first directory of `candidates` that holds the Npcap library, if any.
pub fn find_npcap_directory(candidates: &[PathBuf]) -> Option<PathBuf> {
    candidates
        .iter()
        .find(|directory| directory.join(NPCAP_LIBRARY).is_file())
        .cloned()
}

/// The search path with the Npcap directory first, so the worker finds its libraries.
pub fn path_with_npcap(npcap_directory: &Path, current: Option<&OsStr>) -> Result<OsString, JoinPathsError> {
    let existing = current.map(env::split_paths).into_iter().flatten();
    env::join_paths(std::iter::once(npcap_directory.to_path_buf()).chain(existing))
}

/// The command that starts the worker, with the Npcap directory added to its search path.
pub fn worker_command(worker: &Path, npcap_directory: Option<&Path>) -> Result<Command, JoinPathsError> {
    let mut command = Command::new(worker);
    if let Some(directory) = npcap_directory {
        command.env("PATH", path_with_npcap(directory, env::var_os("PATH").as_deref())?);
    }
    Ok(command)
}

/// Stops whatever gives frames, from another thread, so a reader blocked on it comes back.
pub type Stopper = Arc<dyn Fn() + Send + Sync>;

/// Whatever gives the agent captured frames, one at a time.
pub trait FrameSource: Send {
    /// The next frame, or `None` when the source ended. It blocks until a frame comes.
    fn next_frame(&mut self) -> Result<Option<Vec<u8>>, WorkerError>;

    /// A way to stop the source from another thread. By default there is nothing to stop.
    fn stopper(&self) -> Stopper {
        Arc::new(|| {})
    }
}

/// A running capture worker. It is stopped when this value is dropped.
#[derive(Debug)]
pub struct WorkerProcess {
    child: Arc<Mutex<Child>>,
    frames: FrameReader<BufReader<ChildStdout>>,
}

impl WorkerProcess {
    /// Starts the worker. Its input stays open: the worker stops when the agent closes it or dies.
    pub fn spawn(mut command: Command) -> Result<Self, WorkerError> {
        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(WorkerError::Start)?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| WorkerError::Start(io::Error::other("no output pipe")))?;
        Ok(Self {
            child: Arc::new(Mutex::new(child)),
            frames: FrameReader::new(BufReader::new(stdout)),
        })
    }

    /// The next captured frame, or `None` when the worker ended.
    pub fn next_frame(&mut self) -> Result<Option<Vec<u8>>, WorkerError> {
        Ok(self.frames.next_frame()?)
    }
}

impl FrameSource for WorkerProcess {
    fn next_frame(&mut self) -> Result<Option<Vec<u8>>, WorkerError> {
        WorkerProcess::next_frame(self)
    }

    fn stopper(&self) -> Stopper {
        let child = Arc::clone(&self.child);
        Arc::new(move || kill(&child))
    }
}

impl Drop for WorkerProcess {
    fn drop(&mut self) {
        kill(&self.child);
    }
}

fn kill(child: &Mutex<Child>) {
    let Ok(mut child) = child.lock() else {
        return;
    };
    // The worker may already be gone: there is nothing more to do about a failed kill.
    if child.kill().is_ok() {
        let _ = child.wait();
    }
}
