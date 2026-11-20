//! Turns the game messages of the Dofus protocol into the objects of `odd-core`.
//!
//! Pure logic: messages in, objects and issues out. The names of the messages live in `messages`.
#![forbid(unsafe_code)]

mod brisage;
mod decoder;
mod effects;
mod issue;
mod lots;
pub mod messages;
mod periods;
mod stats;

pub use decoder::{Decoder, Direction};
pub use issue::{Decoded, Issue};
