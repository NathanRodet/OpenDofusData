//! The window of the tax collectors of greatest value (`hht`), with its two tabs.

use odd_core::{Payload, Percepteur, Percepteurs};
use odd_wire::Message;

use crate::issue::Decoded;
use crate::messages::{PERCEPTEURS_RESPONSE, percepteurs as field};

/// Reads the answer and gives one object holding both tabs. An answer with no line at all gives nothing.
pub(crate) fn decode_percepteurs(message: &Message<'_>, out: &mut Decoded) {
    let classic = lines_of(message, field::CLASSIC_LINE, out);
    let dungeon = lines_of(message, field::DUNGEON_LINE, out);
    if classic.is_empty() && dungeon.is_empty() {
        return;
    }
    out.payloads
        .push(Payload::Percepteurs(Percepteurs { classic, dungeon }));
}

fn lines_of(message: &Message<'_>, number: u32, out: &mut Decoded) -> Vec<Percepteur> {
    let lines = message
        .all(number)
        .filter_map(|value| value.as_bytes())
        .filter_map(|bytes| Message::parse(bytes).ok());
    let mut found = Vec::new();
    for line in lines {
        match line_of(&line) {
            Some(percepteur) => found.push(percepteur),
            None => out.missing(PERCEPTEURS_RESPONSE, field::LINE_VALUE_BOX),
        }
    }
    found
}

fn line_of(line: &Message<'_>) -> Option<Percepteur> {
    let position = nested(line, field::LINE_POSITION);
    let alliance = nested(line, field::LINE_ALLIANCE);
    Some(Percepteur {
        alliance: text_of(alliance.as_ref(), field::ALLIANCE_NAME),
        tag: text_of(alliance.as_ref(), field::ALLIANCE_TAG),
        owner: text_of(Some(line), field::LINE_OWNER),
        value: value_of(line)?,
        sub_area_id: line.signed(field::LINE_SUB_AREA)?,
        x: coordinate(position.as_ref(), field::POSITION_X),
        y: coordinate(position.as_ref(), field::POSITION_Y),
    })
}

fn value_of(line: &Message<'_>) -> Option<u64> {
    nested(&nested(line, field::LINE_VALUE_BOX)?, field::VALUE_BOX_INNER)?.varint(field::VALUE)
}

fn nested<'a>(message: &Message<'a>, number: u32) -> Option<Message<'a>> {
    Message::parse(message.bytes(number)?).ok()
}

/// A coordinate the game leaves out is 0.
fn coordinate(position: Option<&Message<'_>>, number: u32) -> i32 {
    position
        .and_then(|message| message.signed(number))
        .and_then(|value| i32::try_from(value).ok())
        .unwrap_or_default()
}

fn text_of(message: Option<&Message<'_>>, number: u32) -> String {
    message
        .and_then(|message| message.bytes(number))
        .map(|bytes| String::from_utf8_lossy(bytes).into_owned())
        .unwrap_or_default()
}
