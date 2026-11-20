"""Builds the golden test fixtures from `discover` captures (structure of the messages, no chat, no text).

Run from the OpenDofusData checkout that holds the captures:
    python make_fixtures.py D:\\REPOS\\OpenDofusData\\captures

Only the messages the decoders read are kept. Free text typed by players (mount names, effect 3809) is replaced
by a neutral word so no pseudonym ends up in the repository.
"""

import json
import sys
from pathlib import Path

SOURCES = {
    "hdv-ressource": ("hdv-ressource.jsonl", {"kcy", "jzs"}),
    "hdv-equipement": ("hdv-equipement.jsonl", {"kcy", "jzs"}),
    "hdv-monture": ("hdv-monture.jsonl", {"kcy", "jzs"}),
    "hdv-graphique": ("hdv-graphique.jsonl", {"iqp", "ire"}),
    "hdv-sans-offre": ("hdv-sans-offre.jsonl", {"kcy", "jzs"}),
    "hdv-recherche": ("hdv-recherche.jsonl", {"kcp", "kbj"}),
    "brisage-jet": ("brisage-jet.jsonl", {"kch", "kdr", "jxy", "kag", "kiq"}),
    "brisage-lot": ("brisage-lot.jsonl", {"kch", "kdr", "jxy", "kag", "kiq"}),
    "brisage-multi": ("brisage-multi.jsonl", {"kch", "kdr", "jxy", "kag", "kiq"}),
    "brisage-focus": ("brisage-focus.jsonl", {"kch", "kdr", "jxy", "kag", "kiq"}),
}
NAME_EFFECT = 3809
NEUTRAL_TEXT = b"Test"


def effect_id(node):
    for child in node.get("fields", []):
        if child["number"] == 10:
            return child.get("value")
    return None


def neutralise(fields):
    """Replaces the text of every name effect, in place."""
    for node in fields:
        children = node.get("fields")
        if not children:
            continue
        if effect_id(node) == NAME_EFFECT:
            for child in children:
                if child["number"] == 3 and child.get("length", 0) > 0:
                    child.update(length=len(NEUTRAL_TEXT), packed=list(NEUTRAL_TEXT))
        neutralise(children)


def strip_hex(fields):
    """Drops the byte previews: the `packed` list carries the same bytes and is enough to rebuild the message."""
    for node in fields:
        node.pop("hex", None)
        strip_hex(node.get("fields", []))


def main(directory: Path) -> None:
    out = Path(__file__).parent
    for name, (file, types) in SOURCES.items():
        kept = []
        for line in (directory / file).read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record["type"] in types:
                neutralise(record["fields"])
                strip_hex(record["fields"])
                kept.append({"direction": record["direction"], "type": record["type"], "fields": record["fields"]})
        (out / f"{name}.jsonl").write_text("\n".join(json.dumps(item, separators=(",", ":")) for item in kept) + "\n", encoding="utf-8")
        print(name, len(kept), "messages")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
