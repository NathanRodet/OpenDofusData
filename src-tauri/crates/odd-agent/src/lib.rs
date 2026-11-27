//! From captured frames to decoded objects, and from there to the collector.
//!
//! The decoding path is pure logic, tested on synthetic frames; the agent runs it on a thread and sends the objects.
#![forbid(unsafe_code)]

mod discovery;
mod events;
mod ids;
mod log;
mod pipeline;
mod runtime;

pub use discovery::{MAX_CAPTURE_BYTES, Observation, Recorded, Recorder, describe_message};
pub use events::{EventContext, LogCategory, build_event, describe, is_shared};
pub use ids::new_event_id;
pub use log::{LogLine, LogSink, LogStatus, NOTE_SENT, SUMMARY_SEND_FAILED, notice, problem};
pub use pipeline::Pipeline;
pub use runtime::{Agent, AgentConfig};
