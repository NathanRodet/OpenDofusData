"""Strict schemas of the shared events: a destroyed object (brisage) and a pet upgrade (familier)."""

import json
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from keyserver.schemas import MAX_BATCH_READINGS, MAX_ITEM_ID, STRICT_MODEL, ObservationTime, ServerName

MAX_PAIRS = 40  # runes of a broken object, resources of a pet upgrade
MAX_QUANTITY = 1_000_000_000
MAX_COEFFICIENT = 10.0  # 0.5 is 50 %; a figure far above 1 is a decoding mistake, not a game value
MAX_PET_LEVEL = 1000
MAX_EXPERIENCE = 1_000_000_000_000
PAIR_SIZE = 2


def _item_and_quantity(pair: list[int]) -> list[int]:
    """[item id, quantity] with both inside the game's bounds (strict mode already refuses booleans)."""
    item_id, quantity = pair
    if not 1 <= item_id <= MAX_ITEM_ID or not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError("item id or quantity out of bounds")
    return pair


Pair = Annotated[list[int], Field(min_length=PAIR_SIZE, max_length=PAIR_SIZE), AfterValidator(_item_and_quantity)]
Pairs = Annotated[list[Pair], Field(min_length=1, max_length=MAX_PAIRS)]
RunePairs = Annotated[list[Pair], Field(max_length=MAX_PAIRS)]  # an object can be broken without giving any rune
Quantity = Annotated[int, Field(ge=1, le=MAX_QUANTITY)]


class BrokenEvent(BaseModel):
    """One object broken at the Concasseur: its coefficient (0.5 is 50 %) and the runes obtained."""

    model_config = STRICT_MODEL

    server: ServerName
    item_id: int = Field(ge=1, le=MAX_ITEM_ID)
    quantity: Quantity
    coefficient: float = Field(ge=0, le=MAX_COEFFICIENT)
    runes: RunePairs
    observed_at: ObservationTime


class PetState(BaseModel):
    """What a pet shows: level, experience (current and maximum), prospection; unknown figures are null."""

    model_config = STRICT_MODEL

    level: int | None = Field(ge=0, le=MAX_PET_LEVEL)
    experience: int | None = Field(ge=0, le=MAX_EXPERIENCE)
    experience_max: int | None = Field(ge=0, le=MAX_EXPERIENCE)
    prospection: int | None = Field(ge=0, le=MAX_EXPERIENCE)


class PetEvent(BaseModel):
    """One pet upgrade: the resources given and the pet before and after."""

    model_config = STRICT_MODEL

    server: ServerName
    pet_item_id: int = Field(ge=1, le=MAX_ITEM_ID)
    resources: Pairs
    before: PetState
    after: PetState
    observed_at: ObservationTime


class BrokenBatch(BaseModel):
    """What a player sends to `POST /brisages`."""

    model_config = STRICT_MODEL

    events: list[BrokenEvent] = Field(min_length=1, max_length=MAX_BATCH_READINGS)


class PetBatch(BaseModel):
    """What a player sends to `POST /familiers`."""

    model_config = STRICT_MODEL

    events: list[PetEvent] = Field(min_length=1, max_length=MAX_BATCH_READINGS)


def payload_text(event: BaseModel) -> str:
    """The event without its date as canonical JSON text: what is stored and what makes two events the same."""
    return json.dumps(event.model_dump(mode="json", exclude={"observed_at"}), sort_keys=True, separators=(",", ":"))
