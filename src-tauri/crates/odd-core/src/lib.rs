//! Wire format of the objects the agent sends to the collector.
//!
//! Pure data: no network, no game protocol. The agent builds these values, the server reads them.
#![forbid(unsafe_code)]

mod brisage;
mod effect;
mod event;
mod lots;
mod percepteurs;
mod roaming;
mod slot;
mod stats;
mod unmapped;
mod validate;

pub use brisage::{Brisage, BrisageItem, Rune};
pub use effect::Effect;
pub use event::{Event, Payload, SCHEMA_VERSION};
pub use lots::{HdvLots, Listing, Lot, Offer};
pub use percepteurs::{Percepteur, Percepteurs};
pub use roaming::{PercepteurSeen, PercepteurSheet};
pub use slot::{Slot, slot_of};
pub use stats::{HdvCategory, HdvStats, Period, Periods, Point, Points};
pub use unmapped::Unmapped;
pub use validate::{
    MAX_CATEGORY_ITEMS, MAX_EFFECTS, MAX_LOTS, MAX_OFFERS_PER_ITEM, MAX_PERCEPTEURS, MAX_POINTS_PER_SERIES, MAX_RUNES,
    MAX_TEXT_CHARS, MAX_UNMAPPED, Violation,
};
