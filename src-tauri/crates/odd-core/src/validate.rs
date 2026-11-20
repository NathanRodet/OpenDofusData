//! Size limits and shape checks the collector applies, and the agent applies before sending.

use crate::brisage::Brisage;
use crate::effect::Effect;
use crate::event::{Event, Payload, SCHEMA_VERSION};
use crate::lots::{HdvLots, Listing};
use crate::stats::{HdvCategory, HdvStats};
use crate::unmapped::Unmapped;

/// Offers allowed for one item (the biggest list seen has 801).
pub const MAX_OFFERS_PER_ITEM: usize = 1500;
/// Effects allowed for one item or offer.
pub const MAX_EFFECTS: usize = 128;
/// Characters allowed in a text of the game.
pub const MAX_TEXT_CHARS: usize = 256;
/// Unmapped fields allowed for one effect, offer or item.
pub const MAX_UNMAPPED: usize = 64;
/// Points allowed in one series of the market graph.
pub const MAX_POINTS_PER_SERIES: usize = 2000;
/// Items allowed in one category listing.
pub const MAX_CATEGORY_ITEMS: usize = 10_000;
/// Runes allowed in one breaking result.
pub const MAX_RUNES: usize = 64;
/// Lot sizes allowed in one resource listing.
pub const MAX_LOTS: usize = 16;

/// Why an event is refused.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum Violation {
    /// The schema version is not the one this build reads.
    #[error("unsupported schema version {schema}")]
    UnsupportedSchema {
        /// The schema version received.
        schema: u32,
    },
    /// More offers than allowed.
    #[error("{count} offers (the maximum is {MAX_OFFERS_PER_ITEM})")]
    TooManyOffers {
        /// Number of offers received.
        count: usize,
    },
    /// More effects than allowed on one item or offer.
    #[error("{count} effects (the maximum is {MAX_EFFECTS})")]
    TooManyEffects {
        /// Number of effects received.
        count: usize,
    },
    /// A text is too long.
    #[error("a text of {chars} characters (the maximum is {MAX_TEXT_CHARS})")]
    TextTooLong {
        /// Length of the text in characters.
        chars: usize,
    },
    /// More unmapped fields than allowed.
    #[error("{count} unmapped fields (the maximum is {MAX_UNMAPPED})")]
    TooManyUnmapped {
        /// Number of unmapped fields received.
        count: usize,
    },
    /// A list is longer than allowed.
    #[error("{what}: {count} entries (the maximum is {limit})")]
    TooLong {
        /// Which list.
        what: &'static str,
        /// Number of entries received.
        count: usize,
        /// Entries allowed.
        limit: usize,
    },
    /// The coefficient is not a finite non-negative number.
    #[error("the coefficient is not a finite non-negative number")]
    InvalidCoefficient,
}

impl Event {
    /// Checks the event against the limits. Returns every violation found.
    pub fn validate(&self) -> Result<(), Vec<Violation>> {
        let mut found = Vec::new();
        if self.schema != SCHEMA_VERSION {
            found.push(Violation::UnsupportedSchema { schema: self.schema });
        }
        match &self.payload {
            Payload::HdvLots(lots) => check_lots(lots, &mut found),
            Payload::HdvStats(stats) => check_stats(stats, &mut found),
            Payload::HdvCategory(category) => check_category(category, &mut found),
            Payload::Brisage(breaking) => check_brisage(breaking, &mut found),
        }
        if found.is_empty() { Ok(()) } else { Err(found) }
    }
}

fn check_len(what: &'static str, count: usize, limit: usize, found: &mut Vec<Violation>) {
    if count > limit {
        found.push(Violation::TooLong { what, count, limit });
    }
}

fn check_unmapped(unmapped: &[Unmapped], found: &mut Vec<Violation>) {
    if unmapped.len() > MAX_UNMAPPED {
        found.push(Violation::TooManyUnmapped { count: unmapped.len() });
    }
}

fn check_effects(effects: &[Effect], found: &mut Vec<Violation>) {
    if effects.len() > MAX_EFFECTS {
        found.push(Violation::TooManyEffects { count: effects.len() });
    }
    for effect in effects {
        if let Some(text) = &effect.text {
            let chars = text.chars().count();
            if chars > MAX_TEXT_CHARS {
                found.push(Violation::TextTooLong { chars });
            }
        }
        check_unmapped(&effect.unmapped, found);
    }
}

fn check_lots(lots: &HdvLots, found: &mut Vec<Violation>) {
    match &lots.listing {
        Listing::Lots { lots } => check_len("lots", lots.len(), MAX_LOTS, found),
        Listing::Offers { offers } => {
            if offers.len() > MAX_OFFERS_PER_ITEM {
                found.push(Violation::TooManyOffers { count: offers.len() });
            }
            for offer in offers {
                check_effects(&offer.effects, found);
                check_unmapped(&offer.unmapped, found);
            }
        }
    }
}

fn check_stats(stats: &HdvStats, found: &mut Vec<Violation>) {
    check_len("hourly points", stats.points.hourly.len(), MAX_POINTS_PER_SERIES, found);
    check_len("daily points", stats.points.daily.len(), MAX_POINTS_PER_SERIES, found);
}

fn check_category(category: &HdvCategory, found: &mut Vec<Violation>) {
    check_len("category items", category.item_ids.len(), MAX_CATEGORY_ITEMS, found);
}

fn check_brisage(breaking: &Brisage, found: &mut Vec<Violation>) {
    if !breaking.coefficient.is_finite() || breaking.coefficient < 0.0 {
        found.push(Violation::InvalidCoefficient);
    }
    check_effects(&breaking.item.effects, found);
    check_unmapped(&breaking.item.unmapped, found);
    check_len("runes", breaking.runes.len(), MAX_RUNES, found);
}
