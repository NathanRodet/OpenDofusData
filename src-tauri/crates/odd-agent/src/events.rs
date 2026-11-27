//! Making the objects to send out of what was decoded, and describing them for the logs of the interface.

use odd_core::{Event, Listing, Payload, SCHEMA_VERSION};
use time::format_description::well_known::Rfc3339;
use time::{OffsetDateTime, UtcOffset};

const PERCENT: f32 = 100.0;

/// What every object of a session shares.
#[derive(Debug, Clone, Copy)]
pub struct EventContext<'a> {
    /// The game server the player chose.
    pub game_server: &'a str,
    /// The version of this application.
    pub client_version: &'a str,
}

/// The family of an object, as the logs show it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LogCategory {
    /// The auction house.
    Hdv,
    /// Breaking items into runes.
    Brisage,
    /// The tax collectors of greatest value.
    Percepteurs,
}

/// Wraps a decoded payload into the object sent to the collector. The date is sent in UTC.
pub fn build_event(
    payload: Payload,
    observed_at: OffsetDateTime,
    event_id: String,
    context: &EventContext<'_>,
) -> Event {
    let utc = observed_at.to_offset(UtcOffset::UTC);
    Event {
        schema: SCHEMA_VERSION,
        event_id,
        observed_at: utc.format(&Rfc3339).unwrap_or_default(),
        game_server: context.game_server.to_owned(),
        client_version: context.client_version.to_owned(),
        payload,
    }
}

/// Whether the player lets this kind of object leave the application. Only the tax collectors can be refused.
pub fn is_shared(payload: &Payload, share_percepteurs: bool) -> bool {
    share_percepteurs
        || !matches!(
            payload,
            Payload::Percepteurs(_) | Payload::PercepteurSeen(_) | Payload::PercepteurSheet(_)
        )
}

/// The item a payload is about; a whole category has none.
pub fn item_id(payload: &Payload) -> Option<i64> {
    match payload {
        Payload::HdvLots(lots) => Some(lots.item_id),
        Payload::HdvStats(stats) => Some(stats.item_id),
        Payload::Brisage(breaking) => Some(breaking.item.id),
        Payload::HdvCategory(_)
        | Payload::Percepteurs(_)
        | Payload::PercepteurSeen(_)
        | Payload::PercepteurSheet(_) => None,
    }
}

/// The type of items a payload is about: only a whole category of the auction house is.
pub fn item_type_id(payload: &Payload) -> Option<i64> {
    match payload {
        Payload::HdvCategory(category) => Some(category.item_type_id),
        _ => None,
    }
}

/// A short French sentence about a payload, with its family.
pub fn describe(payload: &Payload) -> (LogCategory, String) {
    match payload {
        Payload::HdvLots(lots) => (LogCategory::Hdv, describe_listing(lots.item_id, &lots.listing)),
        Payload::HdvStats(stats) => (
            LogCategory::Hdv,
            format!("Statistiques de prix de l'objet {}", stats.item_id),
        ),
        Payload::HdvCategory(category) => {
            let count = category.item_ids.len();
            (
                LogCategory::Hdv,
                format!(
                    "{count} {} en vente dans le type {}",
                    plural(count, "objet"),
                    category.item_type_id
                ),
            )
        }
        Payload::Brisage(breaking) => {
            let percent = breaking.coefficient * PERCENT;
            (
                LogCategory::Brisage,
                format!("Brisage de l'objet {}, coefficient {percent:.0} %", breaking.item.id),
            )
        }
        Payload::Percepteurs(window) => (
            LogCategory::Percepteurs,
            format!(
                "Percepteurs de plus grande valeur: {} en classique, {} en donjon",
                window.classic.len(),
                window.dungeon.len()
            ),
        ),
        Payload::PercepteurSeen(seen) => (
            LogCategory::Percepteurs,
            format!(
                "Percepteur de l'alliance {} croisé sur la carte {}, case {}",
                seen.alliance, seen.map_id, seen.cell
            ),
        ),
        Payload::PercepteurSheet(sheet) => (
            LogCategory::Percepteurs,
            format!(
                "Fiche d'un percepteur de l'alliance {}: {} pods, valeur {} kamas",
                sheet.alliance, sheet.pods, sheet.value
            ),
        ),
    }
}

fn describe_listing(item_id: i64, listing: &Listing) -> String {
    match listing {
        Listing::Offers { offers } if offers.is_empty() => format!("Aucune offre pour l'objet {item_id}"),
        Listing::Offers { offers } => format!(
            "{} {} pour l'objet {item_id}",
            offers.len(),
            plural(offers.len(), "offre")
        ),
        Listing::Lots { lots } => format!("{} tailles de lots pour l'objet {item_id}", lots.len()),
    }
}

fn plural(count: usize, word: &str) -> String {
    if count > 1 { format!("{word}s") } else { word.to_owned() }
}
