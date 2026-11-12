"""The data categories (everything is always collected) and the category of each record."""

from opendofusdata.records import BrokenItem, LotPrice, MarketStats, PetFeeding, Record

CATEGORY_HDV = "hdv"
CATEGORY_BREAKING = "breaking"
CATEGORY_PETS = "pets"

CATEGORY_LABELS = {
    CATEGORY_HDV: "HDV",
    CATEGORY_BREAKING: "Brisage",
    CATEGORY_PETS: "Familier",
}

CATEGORY_BY_TYPE: dict[type, str] = {
    LotPrice: CATEGORY_HDV,
    MarketStats: CATEGORY_HDV,
    PetFeeding: CATEGORY_PETS,
    BrokenItem: CATEGORY_BREAKING,
}


def category_of(record: Record) -> str | None:
    """The data category of a record; None for a type nobody declared."""
    return CATEGORY_BY_TYPE.get(type(record))
