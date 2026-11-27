//! The tax collectors met on a map: the map entry (`jnj`) lists them, opening one (`ilx`) then gives its dialog (`iku`).

use std::collections::HashMap;

use odd_core::{Payload, PercepteurSeen, PercepteurSheet};
use odd_wire::Message;

use crate::effects::unmapped_fields;
use crate::issue::Decoded;
use crate::messages::{PERCEPTEUR_SHEET, roaming as field};

/// Remembers the map the player is on and the collectors of it, so a dialog can be placed on the map.
#[derive(Debug, Default)]
pub(crate) struct RoamingTracker {
    map_id: i64,
    cells: HashMap<i64, i64>,
    opened: Option<(i64, i64)>,
}

impl RoamingTracker {
    /// The player entered a map: gives one object per collector standing on it.
    pub(crate) fn on_map(&mut self, entry: &Message<'_>, out: &mut Decoded) {
        self.map_id = entry.signed(field::MAP_ID).unwrap_or_default();
        self.cells.clear();
        self.opened = None;
        let sub_area_id = entry.signed(field::MAP_SUB_AREA).unwrap_or_default();
        for actor in entry.all(field::MAP_ACTOR).filter_map(|value| value.as_bytes()) {
            let Some(seen) = Message::parse(actor)
                .ok()
                .and_then(|actor| self.seen(&actor, sub_area_id))
            else {
                continue;
            };
            out.payloads.push(Payload::PercepteurSeen(seen));
        }
    }

    /// The player opened the dialog of an entity of a map.
    pub(crate) fn on_opened(&mut self, opened: &Message<'_>) {
        self.opened = opened
            .signed(field::OPENED_MAP)
            .zip(opened.signed(field::OPENED_ENTITY));
    }

    /// The dialog of the collector that was just opened.
    pub(crate) fn on_sheet(&mut self, sheet: &Message<'_>, out: &mut Decoded) {
        let Some((map_id, entity)) = self.opened.take() else {
            return;
        };
        let Some(&cell) = self.cells.get(&entity).filter(|_| map_id == self.map_id) else {
            return out.missing(PERCEPTEUR_SHEET, field::OPENED_ENTITY);
        };
        match sheet_of(sheet, map_id, cell) {
            Some(sheet) => out.payloads.push(Payload::PercepteurSheet(sheet)),
            None => out.missing(PERCEPTEUR_SHEET, field::SHEET_VALUE),
        }
    }

    fn seen(&mut self, actor: &Message<'_>, sub_area_id: i64) -> Option<PercepteurSeen> {
        let collector = nested(
            &nested(&nested(actor, field::ACTOR_BODY)?, field::BODY_KIND)?,
            field::KIND_COLLECTOR,
        )?;
        let collector = nested(&collector, field::COLLECTOR_DATA)?;
        let position = nested(actor, field::ACTOR_POSITION)?;
        let cell = position.signed(field::POSITION_CELL)?;
        self.cells.insert(actor.signed(field::ACTOR_ENTITY)?, cell);
        let alliance = nested(&collector, field::DATA_ALLIANCE);
        Some(PercepteurSeen {
            map_id: self.map_id,
            sub_area_id,
            cell,
            direction: position.signed(field::POSITION_DIRECTION),
            alliance: text(alliance.as_ref(), field::ALLIANCE_NAME),
            tag: text(alliance.as_ref(), field::ALLIANCE_TAG),
            name_ids: [field::DATA_NAME_FIRST, field::DATA_NAME_SECOND]
                .iter()
                .filter_map(|number| collector.signed(*number))
                .collect(),
            emblem: alliance
                .and_then(|alliance| nested(&alliance, field::ALLIANCE_EMBLEM))
                .map(|emblem| unmapped_fields(&emblem, &[]))
                .unwrap_or_default(),
        })
    }
}

fn sheet_of(sheet: &Message<'_>, map_id: i64, cell: i64) -> Option<PercepteurSheet> {
    let alliance = nested(sheet, field::SHEET_ALLIANCE);
    Some(PercepteurSheet {
        map_id,
        cell,
        alliance: text(alliance.as_ref(), field::ALLIANCE_NAME),
        tag: text(alliance.as_ref(), field::ALLIANCE_TAG),
        alliance_collectors: sheet.varint(field::SHEET_ALLIANCE_COLLECTORS).unwrap_or_default(),
        pod_capacity: sheet.varint(field::SHEET_POD_CAPACITY).unwrap_or_default(),
        prospecting: sheet.varint(field::SHEET_PROSPECTING).unwrap_or_default(),
        pods: sheet.varint(field::SHEET_PODS).unwrap_or_default(),
        value: sheet.varint(field::SHEET_VALUE)?,
    })
}

fn nested<'a>(message: &Message<'a>, number: u32) -> Option<Message<'a>> {
    Message::parse(message.bytes(number)?).ok()
}

fn text(message: Option<&Message<'_>>, number: u32) -> String {
    message
        .and_then(|message| message.bytes(number))
        .map(|bytes| String::from_utf8_lossy(bytes).into_owned())
        .unwrap_or_default()
}
