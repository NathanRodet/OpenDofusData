//! From captured frames to decoded objects, and from there to the collector.
//!
//! The decoding path is pure logic, tested on synthetic frames; the agent runs it on a thread and sends the objects.
#![forbid(unsafe_code)]

mod events;
mod ids;
mod log;
mod pipeline;
mod runtime;

pub use events::{EventContext, LogCategory, build_event, describe};
pub use ids::new_event_id;
pub use log::{LogLine, LogSink, LogStatus, NOTE_SENT, SUMMARY_SEND_FAILED, problem};
pub use pipeline::Pipeline;
pub use runtime::{Agent, AgentConfig};
