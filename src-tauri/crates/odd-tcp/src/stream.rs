//! One direction of one connection: puts the segments back in order.

/// Bytes waiting for an earlier segment, at most. Beyond it the missing bytes are declared lost.
pub const MAX_PENDING_BYTES: usize = 256 * 1024;
const MAX_PENDING_SEGMENTS: usize = 512;

/// What a direction hands over.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum Delivery {
    /// The next bytes of the stream, in order.
    Data(Vec<u8>),
    /// Bytes are missing before the data that follows.
    Gap,
}

#[derive(Debug, Default)]
pub(crate) struct Stream {
    next: Option<u32>,
    pending: Vec<(u32, Vec<u8>)>,
    pending_bytes: usize,
}

impl Stream {
    /// Takes a segment, returns what can now be delivered.
    pub(crate) fn push(&mut self, seq: u32, syn: bool, payload: &[u8]) -> Vec<Delivery> {
        let first_byte = if syn { seq.wrapping_add(1) } else { seq };
        let next = *self.next.get_or_insert(first_byte);
        if payload.is_empty() {
            return Vec::new();
        }
        let ahead = first_byte.wrapping_sub(next) as i32;
        if ahead > 0 {
            return self.hold(first_byte, payload);
        }
        let skip = usize::try_from(-i64::from(ahead)).unwrap_or(usize::MAX);
        let mut out = Vec::new();
        self.deliver(payload.get(skip..).unwrap_or(&[]), &mut out);
        out
    }

    fn deliver(&mut self, bytes: &[u8], out: &mut Vec<Delivery>) {
        if bytes.is_empty() {
            return;
        }
        let next = self.next.unwrap_or_default();
        self.next = Some(next.wrapping_add(u32::try_from(bytes.len()).unwrap_or(u32::MAX)));
        out.push(Delivery::Data(bytes.to_vec()));
        self.release_ready(out);
    }

    /// Delivers the waiting segments that now follow, and forgets those that are already covered.
    fn release_ready(&mut self, out: &mut Vec<Delivery>) {
        while let Some(index) = self.ready_index() {
            let (seq, bytes) = self.pending.swap_remove(index);
            self.pending_bytes -= bytes.len();
            let next = self.next.unwrap_or_default();
            let skip = usize::try_from(next.wrapping_sub(seq) as i32).unwrap_or(0);
            let fresh = bytes.get(skip..).unwrap_or(&[]).to_vec();
            self.deliver(&fresh, out);
        }
    }

    fn ready_index(&self) -> Option<usize> {
        let next = self.next?;
        self.pending
            .iter()
            .position(|(seq, _)| (seq.wrapping_sub(next) as i32) <= 0)
    }

    fn hold(&mut self, seq: u32, payload: &[u8]) -> Vec<Delivery> {
        let too_much =
            self.pending_bytes + payload.len() > MAX_PENDING_BYTES || self.pending.len() >= MAX_PENDING_SEGMENTS;
        self.pending.push((seq, payload.to_vec()));
        self.pending_bytes += payload.len();
        if !too_much {
            return Vec::new();
        }
        self.give_up_waiting()
    }

    /// Gives up the missing bytes: continues from the earliest waiting segment.
    fn give_up_waiting(&mut self) -> Vec<Delivery> {
        let next = self.next.unwrap_or_default();
        self.next = self
            .pending
            .iter()
            .map(|(seq, _)| *seq)
            .min_by_key(|seq| seq.wrapping_sub(next));
        let mut out = vec![Delivery::Gap];
        self.release_ready(&mut out);
        out
    }
}
