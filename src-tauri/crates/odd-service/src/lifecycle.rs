//! The life of the agent: restarting it when the settings change, checking the key, turning its lines into logs.

use std::sync::atomic::Ordering;
use std::sync::{Arc, MutexGuard, Weak};

use odd_agent::{Agent, AgentConfig, LogLine, LogSink, NOTE_SENT, SUMMARY_SEND_FAILED, problem};

use crate::check::run_check;
use crate::dto::ConnectionKind;
use crate::factory::SourceError;
use crate::knowledge::{Knowledge, to_entry};
use crate::service::{Inner, State};
use crate::settings::{Settings, normalize_server_url};

/// The folder of the dev mode capture files, in the configuration folder.
const CAPTURE_FOLDER: &str = "captures";

impl Inner {
    pub(crate) fn lock(&self) -> MutexGuard<'_, State> {
        self.state.lock().unwrap_or_else(std::sync::PoisonError::into_inner)
    }

    /// Stops the agent, then starts one for the current settings and checks the key.
    pub(crate) async fn restart(self: &Arc<Self>) {
        let (old, settings, generation) = {
            let mut state = self.lock();
            state.generation += 1;
            state.knowledge = Knowledge::fresh(!state.settings.api_key.trim().is_empty());
            (state.agent.take(), state.settings.clone(), state.generation)
        };
        if let Some(agent) = old {
            agent.stop().await;
        }
        let agent = self.start_agent(&settings);
        self.lock().agent = agent;
        if !settings.api_key.trim().is_empty() {
            let inner = Arc::clone(self);
            self.runtime
                .spawn(async move { inner.check_key(settings, generation).await });
        }
    }

    /// The folder where the dev mode capture writes its files.
    pub(crate) fn capture_dir(&self) -> std::path::PathBuf {
        self.config.config_dir.join(CAPTURE_FOLDER)
    }

    fn start_agent(self: &Arc<Self>, settings: &Settings) -> Option<Agent> {
        let source = match self.factory.open() {
            Ok(source) => source,
            Err(error) => {
                self.emit(&source_problem(&error));
                return None;
            }
        };
        let config = AgentConfig {
            server_url: normalize_server_url(&settings.server_url),
            api_key: settings.api_key.clone(),
            game_server: settings.game_server.clone(),
            client_version: self.config.app_version.clone(),
            capture_dir: settings.dev_capture.then(|| self.capture_dir()),
            capture_detail: settings.capture_types(),
        };
        let weak: Weak<Inner> = Arc::downgrade(self);
        let sink: LogSink = Arc::new(move |line| {
            if let Some(inner) = weak.upgrade() {
                inner.emit(&line);
            }
        });
        Agent::start(config, source, &self.runtime, sink)
            .map_err(|error| self.emit(&problem("L'adresse du serveur n'est pas valide", &error.to_string())))
            .ok()
    }

    async fn check_key(&self, settings: Settings, generation: u64) {
        let result = run_check(&settings.server_url, &settings.api_key).await;
        let mut state = self.lock();
        if state.generation == generation {
            state.knowledge.apply(&result);
        }
    }

    pub(crate) fn emit(&self, line: &LogLine) {
        match (line.summary.as_str(), line.note.as_str()) {
            (SUMMARY_SEND_FAILED, _) => self.lock().knowledge.connection = ConnectionKind::Offline,
            (_, NOTE_SENT) => self.lock().knowledge.connection = ConnectionKind::Connected,
            _ => {}
        }
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let mut entry = to_entry(id, line);
        entry.summary = self.names().summary(&entry.summary, line.item_id, line.item_type_id);
        (self.emitter)(entry);
    }
}

fn source_problem(error: &SourceError) -> LogLine {
    match error {
        SourceError::NpcapMissing | SourceError::WorkerMissing => problem(
            "Npcap est introuvable",
            "Installe Npcap pour que l'application puisse lire le trafic du jeu",
        ),
        SourceError::Start(reason) => problem("La capture n'a pas pu démarrer", reason),
    }
}
