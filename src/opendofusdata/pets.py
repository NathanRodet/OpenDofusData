"""Pet tracker: one event per pet upgrade, from the inventory, the feed request and the update."""

import logging

from opendofusdata.framing import Envelope
from opendofusdata.messages import (
    EFFECT_DETAIL_CURRENT_FIELD,
    EFFECT_DETAIL_FIELD,
    EFFECT_DETAIL_MAX_FIELD,
    EFFECT_ID_FIELD,
    EFFECT_PET_EXPERIENCE,
    EFFECT_PET_LEVEL,
    EFFECT_PROSPECTION,
    EFFECT_VALUE_FIELD,
    INVENTORY_ENTRY_FIELD,
    INVENTORY_LIST_TYPE,
    INVENTORY_UPDATE_TYPE,
    OBJECT_EFFECTS_FIELD,
    OBJECT_FIELD,
    OBJECT_INSTANCE_FIELD,
    OBJECT_ITEM_FIELD,
    PET_FEED_PET_FIELD,
    PET_FEED_QUANTITY_FIELD,
    PET_FEED_RESOURCE_FIELD,
    PET_FEED_STACK_FIELD,
    PET_FEED_TYPE,
    PET_UPDATE_ENTRY_FIELD,
    PET_UPDATE_TYPE,
)
from opendofusdata.protobuf import (
    WIRE_TYPE_LENGTH_DELIMITED,
    WIRE_TYPE_VARINT,
    DecodeError,
    Field,
    decode_fields,
    first_field,
)
from opendofusdata.records import PetFeeding, PetState

logger = logging.getLogger(__name__)

MAX_KNOWN_OBJECTS = 20_000  # an inventory is a few thousand objects at most
KnownObject = tuple[int, list[Field]]  # (item id, the object's fields)
Pending = tuple[int, PetState, tuple[tuple[int, int], ...]]  # (pet instance, state before, resources)


def _varint(fields: list[Field], number: int) -> int | None:
    value = first_field(fields, number, WIRE_TYPE_VARINT)
    return value if isinstance(value, int) else None


def _messages(fields: list[Field], number: int) -> list[list[Field]]:
    return [decode_fields(value) for field_number, wire_type, value in fields
            if field_number == number and wire_type == WIRE_TYPE_LENGTH_DELIMITED and isinstance(value, bytes)]


def _read_object(entry: list[Field], number: int) -> tuple[int, KnownObject] | None:
    """(instance id, (item id, fields)) of the object found in field `number` of an entry."""
    objects = _messages(entry, number)
    if not objects:
        return None
    instance, item = _varint(objects[0], OBJECT_INSTANCE_FIELD), _varint(objects[0], OBJECT_ITEM_FIELD)
    return (instance, (item, objects[0])) if instance is not None and item else None


def _apply_effect(effect: list[Field], values: dict[str, int | None]) -> None:
    effect_id = _varint(effect, EFFECT_ID_FIELD)
    detail = (_messages(effect, EFFECT_DETAIL_FIELD) or [[]])[0]
    if effect_id == EFFECT_PROSPECTION:
        values["prospection"] = _varint(effect, EFFECT_VALUE_FIELD)
    elif effect_id == EFFECT_PET_LEVEL:
        values["level"] = _varint(detail, EFFECT_DETAIL_CURRENT_FIELD)
    elif effect_id == EFFECT_PET_EXPERIENCE:
        values["experience"] = _varint(detail, EFFECT_DETAIL_CURRENT_FIELD)
        values["experience_max"] = _varint(detail, EFFECT_DETAIL_MAX_FIELD)


def pet_state_of(object_fields: list[Field]) -> PetState:
    """Level, experience and prospection read from the effects of a pet object."""
    values: dict[str, int | None] = {"level": None, "experience": None, "experience_max": None,
                                     "prospection": None}
    for effect in _messages(object_fields, OBJECT_EFFECTS_FIELD):
        _apply_effect(effect, values)
    return PetState(**values)


class PetTracker:
    """Follows the inventory, the pet feed requests and the pet updates sent by the server."""

    def __init__(self, server: str) -> None:
        self._server = server
        self._objects: dict[int, KnownObject] = {}
        self._pending: Pending | None = None

    def feed(self, envelope: Envelope, from_server: bool, captured_at: str) -> PetFeeding | None:
        """Update what is known; return the event when an update completes a pet upgrade."""
        try:
            return self._handle(envelope, from_server, captured_at)
        except DecodeError as error:
            logger.warning("unreadable %s message: %s", envelope.type_name, error)
            return None

    def _handle(self, envelope: Envelope, from_server: bool, captured_at: str) -> PetFeeding | None:
        kind = envelope.type_name
        if from_server and kind == INVENTORY_LIST_TYPE:
            self._load_inventory(envelope.payload)
        elif from_server and kind == INVENTORY_UPDATE_TYPE:
            self._add_to_inventory(envelope.payload)
        elif not from_server and kind == PET_FEED_TYPE:
            self._request(envelope.payload)
        elif from_server and kind == PET_UPDATE_TYPE:
            return self._updated(envelope.payload, captured_at)
        return None

    def _load_inventory(self, payload: bytes) -> None:
        objects: dict[int, KnownObject] = {}
        for entry in _messages(decode_fields(payload), INVENTORY_ENTRY_FIELD):
            read = _read_object(entry, OBJECT_FIELD)
            if read is not None and len(objects) < MAX_KNOWN_OBJECTS:
                objects[read[0]] = read[1]
        self._objects, self._pending = objects, None

    def _add_to_inventory(self, payload: bytes) -> None:
        """Objects announced after login (loot, crafted items, runes): added to what is known."""
        for entry in _messages(decode_fields(payload), INVENTORY_ENTRY_FIELD):
            read = _read_object(entry, OBJECT_FIELD)
            if read is not None:
                self._remember(read[0], read[1])

    def _request(self, payload: bytes) -> None:
        fields = decode_fields(payload)
        pet_instance = _varint(fields, PET_FEED_PET_FIELD)
        pet = self._objects.get(pet_instance) if pet_instance is not None else None
        resources = self._resources(_messages(fields, PET_FEED_RESOURCE_FIELD))
        self._pending = None
        if pet is None:
            logger.info("pet feeding skipped: pet %s is not in the known inventory", pet_instance)
        elif resources:
            self._pending = (pet_instance, pet_state_of(pet[1]), resources)

    def _resources(self, requested: list[list[Field]]) -> tuple[tuple[int, int], ...]:
        resources = []
        for resource in requested:
            stack = _varint(resource, PET_FEED_STACK_FIELD)
            known = self._objects.get(stack) if stack is not None else None
            quantity = _varint(resource, PET_FEED_QUANTITY_FIELD)
            if known is None or not quantity:
                logger.info("pet feeding skipped: stack %s is not in the known inventory", stack)
                return ()
            resources.append((known[0], quantity))
        return tuple(resources)

    def _remember(self, instance: int, known: KnownObject) -> None:
        if instance not in self._objects and len(self._objects) >= MAX_KNOWN_OBJECTS:
            self._objects.pop(next(iter(self._objects)))  # the oldest known object makes room
        self._objects[instance] = known

    def _updated(self, payload: bytes, captured_at: str) -> PetFeeding | None:
        entries = _messages(decode_fields(payload), PET_UPDATE_ENTRY_FIELD)
        read = _read_object(entries[0], OBJECT_FIELD) if entries else None
        if read is None:
            return None
        instance, known = read
        self._remember(instance, known)
        if self._pending is None or self._pending[0] != instance:
            return None
        _, before, resources = self._pending
        self._pending = None
        return PetFeeding(self._server, known[0], resources, before, pet_state_of(known[1]), captured_at)
