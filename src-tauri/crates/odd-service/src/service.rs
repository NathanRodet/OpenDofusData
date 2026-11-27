//! The service: settings, status, connection test and the life of the agent.

use std::path::PathBuf;
use std::sync::atomic::AtomicU64;
use std::sync::{Arc, Mutex};

use odd_agent::Agent;
use time::OffsetDateTime;
use tokio::runtime::Handle;

use crate::check::{run_check, test_message};
use crate::dto::{AppStatus, ConnectionKind, ConnectionTest, LogEntry, ReceivedProgress, SentProgress, SyncProgress};
use crate::error::ServiceError;
use crate::factory::SourceFactory;
use crate::knowledge::Knowledge;
use crate::naming::Names;
use crate::reference::Counter;
use crate::settings::{Settings, SettingsStore};
use crate::update::Offer;

/// Told about each new line of the logs.
pub type Emitter = Arc<dyn Fn(LogEntry) + Send + Sync>;

/// What the service needs to start.
#[derive(Debug, Clone)]
pub struct ServiceConfig {
    /// The folder of the settings file.
    pub config_dir: PathBuf,
    /// Where a downloaded installer is kept.
    pub download_dir: PathBuf,
    /// The address of the latest release (GitHub API).
    pub releases_url: String,
    /// The address of the DofusDB API.
    pub reference_url: String,
    /// The version of this application.
    pub app_version: String,
}

pub(crate) struct State {
    pub(crate) settings: Settings,
    pub(crate) agent: Option<Agent>,
    pub(crate) knowledge: Knowledge,
    pub(crate) generation: u64,
}

pub(crate) struct Inner {
    pub(crate) config: ServiceConfig,
    pub(crate) store: SettingsStore,
    pub(crate) runtime: Handle,
    pub(crate) factory: Arc<dyn SourceFactory>,
    pub(crate) emitter: Emitter,
    pub(crate) next_id: AtomicU64,
    pub(crate) state: Mutex<State>,
    pub(crate) update: Mutex<Option<Offer>>,
    pub(crate) reference: Mutex<Counter>,
    pub(crate) names: Mutex<Names>,
}

/// The logic behind the interface.
#[derive(Clone)]
pub struct Service {
    pub(crate) inner: Arc<Inner>,
}

impl Service {
    /// Loads the settings and starts the agent.
    pub async fn start(
        config: ServiceConfig,
        runtime: Handle,
        factory: Arc<dyn SourceFactory>,
        emitter: Emitter,
    ) -> Self {
        let store = SettingsStore::new(config.config_dir.clone());
        let settings = store.load();
        let knowledge = Knowledge::fresh(!settings.api_key.trim().is_empty());
        let state = State {
            settings,
            agent: None,
            knowledge,
            generation: 0,
        };
        let inner = Arc::new(Inner {
            config,
            store,
            runtime,
            factory,
            emitter,
            next_id: AtomicU64::new(1),
            state: Mutex::new(state),
            update: Mutex::default(),
            reference: Mutex::default(),
            names: Mutex::default(),
        });
        inner.restart().await;
        tokio::spawn(Arc::clone(&inner).refresh_reference());
        Self { inner }
    }

    /// The settings now.
    pub fn settings(&self) -> Settings {
        self.inner.lock().settings.clone()
    }

    /// Saves the settings and applies them: the agent restarts and the key is checked again.
    pub async fn save_settings(&self, settings: Settings) -> Result<(), ServiceError> {
        self.inner.store.save(&settings)?;
        self.inner.lock().settings = settings;
        self.inner.restart().await;
        Ok(())
    }

    /// The folder where the dev mode capture writes its files.
    pub fn capture_dir(&self) -> PathBuf {
        self.inner.capture_dir()
    }

    /// The state shown at the top of the interface.
    pub fn status(&self) -> AppStatus {
        let (state, now) = (self.inner.lock(), OffsetDateTime::now_utc());
        let has_key = !state.settings.api_key.trim().is_empty();
        let snapshot = state.agent.as_ref().map(Agent::snapshot).unwrap_or_default();
        AppStatus {
            app_version: self.inner.config.app_version.clone(),
            npcap: self.inner.factory.npcap(),
            key: state.knowledge.key_state(has_key, snapshot.key_refused, now),
            key_expires_in_days: if has_key { state.knowledge.days_left(now) } else { None },
            connection: if has_key {
                state.knowledge.connection
            } else {
                ConnectionKind::Offline
            },
            latency_ms: state.knowledge.latency_ms,
            update: self.inner.offered_info(),
        }
    }

    /// The counters of the logs page.
    pub fn sync(&self) -> SyncProgress {
        let snapshot = self
            .inner
            .lock()
            .agent
            .as_ref()
            .map(Agent::snapshot)
            .unwrap_or_default();
        let done = snapshot.stored + snapshot.ignored + snapshot.rejected;
        let pending = u64::try_from(snapshot.pending).unwrap_or(u64::MAX);
        SyncProgress {
            reference: self.inner.reference_progress(),
            sent: SentProgress {
                done,
                total: done + pending,
                pending,
                errors: snapshot.failed_attempts + snapshot.rejected,
            },
            received: ReceivedProgress {
                count: 0,
                last_at: None,
            },
        }
    }

    /// Tries the given settings against the collector, without saving them.
    pub async fn test_connection(&self, settings: Settings) -> ConnectionTest {
        if settings.api_key.trim().is_empty() {
            return ConnectionTest {
                ok: false,
                message: "Colle ta clé d'API.".to_owned(),
            };
        }
        test_message(&run_check(&settings.server_url, &settings.api_key).await)
    }

    /// Forgets the saved settings and goes back to the defaults.
    pub async fn purge(&self) -> Result<(), ServiceError> {
        self.inner.store.remove()?;
        self.inner
            .forget_reference()
            .map_err(|error| ServiceError::Io(std::io::Error::other(error)))?;
        self.inner.lock().settings = Settings::default();
        self.inner.restart().await;
        Ok(())
    }

    /// Stops the agent.
    pub async fn shutdown(&self) {
        let agent = self.inner.lock().agent.take();
        if let Some(agent) = agent {
            agent.stop().await;
        }
    }
}

impl std::fmt::Debug for Service {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("Service(..)")
    }
}
