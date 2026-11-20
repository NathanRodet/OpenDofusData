//! The market graph of an item (`iqp` asks, `ire` answers) and the items for sale in a type (`kbj`).

use odd_core::{HdvCategory, HdvStats, Payload, Point, Points};
use odd_wire::{Message, unpack_varints};
use time::OffsetDateTime;

use crate::issue::Decoded;
use crate::messages::{CATEGORY_RESPONSE, STATS_RESPONSE, category, stats};
use crate::periods::{last_purchase, periods};

/// Remembers the item the last graph was asked for, in case a graph has no points.
#[derive(Debug, Default)]
pub(crate) struct StatsTracker {
    asked: Option<i64>,
}

impl StatsTracker {
    pub(crate) fn on_request(&mut self, request: &Message<'_>) {
        self.asked = request.signed(stats::REQUEST_ITEM);
    }

    pub(crate) fn on_response(&mut self, response: &Message<'_>, now: OffsetDateTime, out: &mut Decoded) {
        let hourly = points_of(response, stats::HOURLY_POINT);
        let daily = points_of(response, stats::DAILY_POINT);
        let item = hourly
            .iter()
            .chain(daily.iter())
            .find_map(|(item, _)| *item)
            .or(self.asked);
        let Some(item_id) = item else {
            return out.missing(STATS_RESPONSE, stats::POINT_ITEM);
        };
        let hourly: Vec<Point> = hourly.into_iter().map(|(_, point)| point).collect();
        let daily: Vec<Point> = daily.into_iter().map(|(_, point)| point).collect();
        out.payloads.push(Payload::HdvStats(HdvStats {
            item_id,
            last_purchase_at: last_purchase(&hourly),
            periods: periods(&hourly, &daily, now),
            points: Points { hourly, daily },
        }));
    }
}

fn points_of(response: &Message<'_>, number: u32) -> Vec<(Option<i64>, Point)> {
    let messages = response
        .all(number)
        .filter_map(|value| value.as_bytes())
        .filter_map(|bytes| Message::parse(bytes).ok());
    messages.filter_map(|point| point_of(&point)).collect()
}

fn point_of(point: &Message<'_>) -> Option<(Option<i64>, Point)> {
    let at = std::str::from_utf8(point.bytes(stats::POINT_AT)?).ok()?.to_owned();
    let value = Point {
        at,
        price: point.signed(stats::POINT_PRICE)?,
        quantity: point.signed(stats::POINT_QUANTITY)?,
    };
    Some((point.signed(stats::POINT_ITEM), value))
}

/// Reads a `kbj` answer: the items of a type that have at least one offer.
pub(crate) fn decode_category(answer: &Message<'_>, out: &mut Decoded) {
    let Some(item_type_id) = answer.signed(category::ITEM_TYPE) else {
        return out.missing(CATEGORY_RESPONSE, category::ITEM_TYPE);
    };
    let packed = answer
        .bytes(category::ITEM_IDS)
        .and_then(|bytes| unpack_varints(bytes).ok());
    let item_ids = packed.unwrap_or_default().into_iter().map(|id| id as i64).collect();
    out.payloads
        .push(Payload::HdvCategory(HdvCategory { item_type_id, item_ids }));
}
