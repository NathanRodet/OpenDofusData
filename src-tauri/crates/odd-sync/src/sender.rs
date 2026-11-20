//! The sending loop: gathers objects for a short while, sends them in one request, and tries again later when the
//! server cannot be reached.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use odd_core::Event;
use tokio::sync::mpsc;
use tokio::task::JoinHandle;
use tokio::time::{Instant, timeout_at};

use crate::client::{EventResult, ServerStatus, SyncClient, SyncError};
use crate::config::{Observer, SenderConfig};
use crate::outbox::Outbox;
use crate::status::{Notice, SyncStatus};

/// Objects that can wait to enter the queue, at most.
const CHANNEL_CAPACITY: usize = 1024;

/// The handle of a running sending loop.
#[derive(Debug)]
pub struct Sender {
    objects: mpsc::Sender<Event>,
    task: JoinHandle<()>,
}

impl Sender {
    /// Queues an object. Returns `false` when too many objects wait and this one is dropped.
    pub fn submit(&self, event: Event) -> bool {
        self.objects.try_send(event).is_ok()
    }

    /// Sends what still waits (one attempt), then stops the loop.
    pub async fn finish(self) {
        drop(self.objects);
        if let Err(error) = self.task.await {
            tracing::warn!(%error, "the sending loop ended abnormally");
        }
    }
}

/// Starts the sending loop on the current Tokio runtime.
pub fn spawn_sender(client: SyncClient, config: SenderConfig, status: Arc<SyncStatus>, observer: Observer) -> Sender {
    let (objects, incoming) = mpsc::channel(CHANNEL_CAPACITY);
    let state = Loop {
        client,
        config,
        status,
        observer,
        outbox: Outbox::new(),
        incoming,
        closed: false,
        backoff: config.backoff_start,
    };
    Sender {
        objects,
        task: tokio::spawn(state.run()),
    }
}

struct Loop {
    client: SyncClient,
    config: SenderConfig,
    status: Arc<SyncStatus>,
    observer: Observer,
    outbox: Outbox,
    incoming: mpsc::Receiver<Event>,
    closed: bool,
    backoff: Duration,
}

impl Loop {
    async fn run(mut self) {
        while self.wait_for_work().await {
            self.gather_for(self.config.batch_window).await;
            if !self.deliver().await {
                break;
            }
        }
    }

    /// Waits until an object is queued. `false` when nothing will ever come.
    async fn wait_for_work(&mut self) -> bool {
        if !self.outbox.is_empty() {
            return true;
        }
        match self.incoming.recv().await {
            Some(event) => {
                self.outbox.push(event);
                true
            }
            None => false,
        }
    }

    /// Queues what comes in for `duration`.
    async fn gather_for(&mut self, duration: Duration) {
        let deadline = Instant::now() + duration;
        while !self.closed {
            match timeout_at(deadline, self.incoming.recv()).await {
                Ok(Some(event)) => {
                    self.outbox.push(event);
                }
                Ok(None) => self.closed = true,
                Err(_) => break,
            }
        }
    }

    /// One attempt. `false` when the loop must stop.
    async fn deliver(&mut self) -> bool {
        let batch = self.outbox.take_batch(self.config.max_batch);
        let keep_going = match self.client.send(&batch).await {
            Ok(results) => self.record(batch, results).await,
            Err(SyncError::KeyRefused) => return self.key_refused(),
            Err(SyncError::Refused { status }) => self.refused(batch, status),
            Err(error) => self.failed(batch, &error.to_string()).await,
        };
        self.status.update(|snapshot| {
            snapshot.pending = self.outbox.len();
            snapshot.dropped = self.outbox.dropped();
        });
        keep_going && !(self.closed && self.outbox.is_empty())
    }

    async fn record(&mut self, batch: Vec<Event>, results: Vec<EventResult>) -> bool {
        let mut by_id: HashMap<String, ServerStatus> = results.into_iter().map(|r| (r.event_id, r.status)).collect();
        let mut retry = Vec::new();
        for event in batch {
            match by_id.remove(&event.event_id).unwrap_or(ServerStatus::Failed) {
                ServerStatus::Failed => retry.push(event),
                status => self.deliver_notice(event, status),
            }
        }
        if retry.is_empty() {
            self.backoff = self.config.backoff_start;
            return true;
        }
        self.failed(retry, "the server could not store some objects").await
    }

    fn deliver_notice(&self, event: Event, status: ServerStatus) {
        self.status.update(|snapshot| match &status {
            ServerStatus::Stored => snapshot.stored += 1,
            ServerStatus::Ignored => snapshot.ignored += 1,
            ServerStatus::Rejected(_) | ServerStatus::Failed => snapshot.rejected += 1,
        });
        (self.observer)(Notice::Delivered {
            event: Box::new(event),
            status,
        });
    }

    fn refused(&mut self, batch: Vec<Event>, status: u16) -> bool {
        for event in batch {
            self.deliver_notice(event, ServerStatus::Rejected(format!("the server answered {status}")));
        }
        true
    }

    fn key_refused(&mut self) -> bool {
        self.status.update(|snapshot| snapshot.key_refused = true);
        (self.observer)(Notice::KeyRefused);
        false
    }

    /// Puts the objects back and waits before the next attempt, still queuing what comes in.
    async fn failed(&mut self, batch: Vec<Event>, reason: &str) -> bool {
        self.outbox.put_back(batch);
        self.status.update(|snapshot| snapshot.failed_attempts += 1);
        tracing::warn!(reason, "sending failed, will try again");
        (self.observer)(Notice::Failed {
            reason: reason.to_owned(),
            waiting: self.outbox.len(),
        });
        if self.closed {
            return false;
        }
        self.gather_for(self.backoff).await;
        self.backoff = (self.backoff * 2).min(self.config.backoff_max);
        true
    }
}
