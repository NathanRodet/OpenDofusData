//! How long each kind of data is kept. The collector refuses older observations and purges what outlives these.

use time::Duration;

use crate::event::Payload;

/// How long data is kept unless its kind says otherwise.
pub const DEFAULT_RETENTION: Duration = Duration::days(30);
/// How long the tax collectors window (the Book) is kept.
pub const PERCEPTEURS_RETENTION: Duration = Duration::hours(4);
/// How long the tax collectors met on a map, and their dialogs, are kept.
pub const PERCEPTEURS_MET_RETENTION: Duration = Duration::hours(12);

/// The kinds of slots (as stored) that are kept less than the default, with how long.
pub const SHORT_RETENTIONS: [(&str, Duration); 3] = [
    ("percepteurs", PERCEPTEURS_RETENTION),
    ("percepteur_seen", PERCEPTEURS_MET_RETENTION),
    ("percepteur_sheet", PERCEPTEURS_MET_RETENTION),
];

/// How long a kind of slot (as stored, such as `percepteur_seen`) is kept.
pub fn retention_of_slot_kind(kind: &str) -> Duration {
    SHORT_RETENTIONS
        .iter()
        .find(|(short, _)| *short == kind)
        .map_or(DEFAULT_RETENTION, |(_, kept)| *kept)
}

impl Payload {
    /// How long this data is kept.
    pub fn retention(&self) -> Duration {
        match self {
            Self::Percepteurs(_) => PERCEPTEURS_RETENTION,
            Self::PercepteurSeen(_) | Self::PercepteurSheet(_) => PERCEPTEURS_MET_RETENTION,
            Self::HdvLots(_) | Self::HdvStats(_) | Self::HdvCategory(_) | Self::Brisage(_) => DEFAULT_RETENTION,
        }
    }
}
