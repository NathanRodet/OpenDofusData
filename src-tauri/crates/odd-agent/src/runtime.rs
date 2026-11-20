//! The agent: reads captured frames, decodes them, sends the objects, and tells the interface what happened.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::{self, JoinHandle};

use odd_capture::{FrameSource, GAME_PORT, Stopper};
use odd_sync::{Sender, SenderConfig, SyncClient, SyncError, SyncSnapshot, SyncStatus, spawn_sender};
use time::OffsetDateTime;
use tokio::runtime::Handle;

use crate::events::{EventContext, build_event};
use crate::ids::new_event_id;
use crate::log::{LogSink, from_notice, problem, unsent};
use crate::pipeline::Pipeline;

/// What the agent needs from the player's settings.
#[derive(Debug, Clone)]
pub struct AgentConfig {
    /// Address of the collector.
    pub server_url: String,
    /// The player's key. Without a key nothing is sent.
    pub api_key: String,
    /// The game server the player chose.
    pub game_server: String,
    /// The version of this application.
    pub client_version: String,
}

/// A running agent.
pub struct Agent {
    reader: JoinHandle<()>,
    sender: Option<Arc<Sender>>,
    status: Arc<SyncStatus>,
    stop: Arc<AtomicBool>,
    stopper: Stopper,
}

impl Agent {
    /// Starts reading `source` on a thread and sending on `runtime`.
    pub fn start(
        config: AgentConfig,
        source: Box<dyn FrameSource>,
        runtime: &Handle,
        sink: LogSink,
    ) -> Result<Self, SyncError> {
        let status = Arc::new(SyncStatus::default());
        let sender = start_sender(&config, runtime, &status, &sink)?.map(Arc::new);
        let stop = Arc::new(AtomicBool::new(false));
        let stopper = source.stopper();
        let reader = Reader {
            source,
            pipeline: Pipeline::new(GAME_PORT),
            sender: sender.clone(),
            sink,
            config,
            stop: Arc::clone(&stop),
        };
        let reader = thread::spawn(move || reader.run());
        Ok(Self {
            reader,
            sender,
            status,
            stop,
            stopper,
        })
    }

    /// The counters of the sending.
    pub fn snapshot(&self) -> SyncSnapshot {
        self.status.snapshot()
    }

    /// Stops reading, sends what still waits, and ends.
    pub async fn stop(self) {
        self.stop.store(true, Ordering::SeqCst);
        (self.stopper)();
        if tokio::task::spawn_blocking(move || self.reader.join()).await.is_err() {
            tracing::warn!("the reading thread could not be waited for");
        }
        if let Some(sender) = self.sender.and_then(|shared| Arc::try_unwrap(shared).ok()) {
            sender.finish().await;
        }
    }
}

fn start_sender(
    config: &AgentConfig,
    runtime: &Handle,
    status: &Arc<SyncStatus>,
    sink: &LogSink,
) -> Result<Option<Sender>, SyncError> {
    if config.api_key.trim().is_empty() {
        return Ok(None);
    }
    let client = SyncClient::new(&config.server_url, config.api_key.trim())?;
    let sink = Arc::clone(sink);
    let observer = Arc::new(move |notice| sink(from_notice(notice)));
    let _guard = runtime.enter();
    Ok(Some(spawn_sender(
        client,
        SenderConfig::default(),
        Arc::clone(status),
        observer,
    )))
}

struct Reader {
    source: Box<dyn FrameSource>,
    pipeline: Pipeline,
    sender: Option<Arc<Sender>>,
    sink: LogSink,
    config: AgentConfig,
    stop: Arc<AtomicBool>,
}

impl Reader {
    fn run(mut self) {
        while !self.stop.load(Ordering::SeqCst) {
            match self.source.next_frame() {
                Ok(Some(frame)) => self.handle(&frame),
                Ok(None) => {
                    return self.ended("La capture s'est arrêtée", "Le programme de capture n'envoie plus rien");
                }
                Err(error) => return self.ended("La capture s'est arrêtée", &error.to_string()),
            }
        }
    }

    fn ended(&self, summary: &str, note: &str) {
        if !self.stop.load(Ordering::SeqCst) {
            (self.sink)(problem(summary, note));
        }
    }

    fn handle(&mut self, frame: &[u8]) {
        let now = OffsetDateTime::now_utc();
        let decoded = self.pipeline.handle_frame(frame, now);
        for issue in decoded.issues {
            (self.sink)(problem("Message du jeu non compris", &issue.to_string()));
        }
        let context = EventContext {
            game_server: &self.config.game_server,
            client_version: &self.config.client_version,
        };
        for payload in decoded.payloads {
            let event = build_event(payload, now, new_event_id(), &context);
            match &self.sender {
                Some(sender) => self.submit(sender, event),
                None => (self.sink)(unsent(&event)),
            }
        }
    }

    fn submit(&self, sender: &Sender, event: odd_core::Event) {
        if !sender.submit(event) {
            (self.sink)(problem("File d'envoi pleine", "Une donnée a été abandonnée"));
        }
    }
}
