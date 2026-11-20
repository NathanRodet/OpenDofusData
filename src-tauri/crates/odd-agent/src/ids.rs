//! Identifiers of the objects sent to the collector, unique so that a repeated send is recognised.

use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

const ID_BYTES: usize = 16;

static FALLBACK_COUNTER: AtomicU64 = AtomicU64::new(0);

/// A new identifier: 128 random bits in hexadecimal. If the system gives no random bytes (it practically never
/// happens), the time and a counter are used instead, which stays unique within this run.
pub fn new_event_id() -> String {
    let mut bytes = [0_u8; ID_BYTES];
    if getrandom::fill(&mut bytes).is_err() {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |elapsed| elapsed.as_nanos());
        let counter = FALLBACK_COUNTER.fetch_add(1, Ordering::Relaxed);
        return format!("{nanos:024x}{counter:08x}");
    }
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}
