//! The contract between the agent and whatever gives it frames.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::collections::VecDeque;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use odd_capture::{FrameSource, Stopper, WorkerError};

struct Queue(VecDeque<Vec<u8>>);

impl FrameSource for Queue {
    fn next_frame(&mut self) -> Result<Option<Vec<u8>>, WorkerError> {
        Ok(self.0.pop_front())
    }
}

struct Stoppable(Arc<AtomicBool>);

impl FrameSource for Stoppable {
    fn next_frame(&mut self) -> Result<Option<Vec<u8>>, WorkerError> {
        Ok(None)
    }

    fn stopper(&self) -> Stopper {
        let flag = Arc::clone(&self.0);
        Arc::new(move || flag.store(true, Ordering::SeqCst))
    }
}

#[test]
fn a_source_gives_its_frames_then_none() {
    let mut source: Box<dyn FrameSource> = Box::new(Queue(VecDeque::from([vec![1], vec![2, 2]])));
    assert_eq!(source.next_frame().unwrap(), Some(vec![1]));
    assert_eq!(source.next_frame().unwrap(), Some(vec![2, 2]));
    assert_eq!(source.next_frame().unwrap(), None);
}

#[test]
fn by_default_stopping_does_nothing() {
    let source = Queue(VecDeque::new());
    (source.stopper())();
}

#[test]
fn a_source_can_hand_out_a_way_to_unblock_it() {
    let flag = Arc::new(AtomicBool::new(false));
    let source = Stoppable(Arc::clone(&flag));
    let stopper = source.stopper();
    stopper();
    assert!(flag.load(Ordering::SeqCst));
}
