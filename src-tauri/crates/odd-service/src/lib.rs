//! The logic of the application behind the interface: settings, status, connection test, life of the agent.
#![forbid(unsafe_code)]

mod check;
mod dto;
mod error;
mod factory;
mod knowledge;
mod lifecycle;
mod logs;
mod naming;
mod reference;
mod service;
mod settings;
mod update;

pub use dto::{
    AppStatus, ConnectionKind, ConnectionTest, EntryCategory, EntryStatus, KeyState, LogEntry, LogOrigin, NpcapState,
    Progress, ReceivedProgress, SentProgress, SyncProgress, UpdateInfo,
};
pub use error::ServiceError;
pub use factory::{SourceError, SourceFactory, WorkerFactory};
pub use service::{Emitter, Service, ServiceConfig};
pub use settings::{DEFAULT_GAME_SERVER, DEFAULT_SERVER_URL, Settings, SettingsStore, normalize_server_url};
