//! Downloads the reference data (items) from DofusDB and keeps a local copy.
#![forbid(unsafe_code)]

mod client;
mod error;
mod fetch;
mod store;

pub use client::{Item, Named, ReferenceClient};
pub use error::ReferenceError;
pub use fetch::Reference;
pub use store::{ReferenceStore, Snapshot};
