"""Visible reasons when a pet upgrade cannot be recorded (the terminal is not where players look)."""

import threading
from datetime import datetime, timezone

import pytest

from opendofusdata.capture_session import CaptureSession
from opendofusdata.log_feed import LogFeed, format_log_row
from opendofusdata.pets import PetTracker
from tests.envelopes import FLOW_KEY
from tests.test_pets import BONE, BONE_STACK, MOMENT, PET, SERVER, feed, inventory, pet_entry, stack_entry, updated
from tests.test_pets_pipeline import CLIENT_KEY

NOW = datetime(2026, 11, 12, 0, 20, tzinfo=timezone.utc)
UNKNOWN_STACK = 999999


def tracker_with_notices() -> tuple[PetTracker, list[str]]:
    notices: list[str] = []
    tracker = PetTracker(SERVER, notices.append)
    tracker.feed(inventory(stack_entry(BONE, BONE_STACK, 4787), pet_entry()), True, MOMENT)
    return tracker, notices


def test_an_unknown_resource_gives_a_notice_with_the_instance_and_the_way_out() -> None:
    tracker, notices = tracker_with_notices()
    tracker.feed(feed(PET, (42, UNKNOWN_STACK)), False, MOMENT)
    assert len(notices) == 1
    assert notices[0] == f"ressource inconnue #{UNKNOWN_STACK}"


def test_an_unknown_pet_gives_a_notice() -> None:
    tracker, notices = tracker_with_notices()
    tracker.feed(feed(123, (100, BONE_STACK)), False, MOMENT)
    assert len(notices) == 1
    assert notices == ["familier inconnu #123"]


def test_a_recorded_upgrade_gives_no_notice() -> None:
    tracker, notices = tracker_with_notices()
    tracker.feed(feed(PET, (100, BONE_STACK)), False, MOMENT)
    assert tracker.feed(updated(pet_entry(experience=262)), True, MOMENT) is not None
    assert notices == []


def test_the_inventory_flag_turns_on_with_the_inventory_list_only() -> None:
    tracker = PetTracker(SERVER)
    assert tracker.inventory_seen is False
    tracker.feed(inventory(pet_entry()), True, MOMENT)
    assert tracker.inventory_seen is True


def test_a_note_is_shown_in_the_name_column() -> None:
    feed_log = LogFeed()
    feed_log.add_note("Familier", "ressource inconnue #5", NOW, "ignorée", "reconnecte")
    row = format_log_row(feed_log.entries()[0], lambda item_id: "never used")
    assert row[1:] == ("Familier", "ressource inconnue #5", "ignorée", "reconnecte")


def run_unknown_feeding(tmp_path) -> tuple[CaptureSession, LogFeed]:
    feed_log = LogFeed()
    done = threading.Event()

    def capture(pipeline, interface, stop) -> None:
        pipeline.on_envelope(inventory(stack_entry(BONE, BONE_STACK, 5), pet_entry()), FLOW_KEY)
        pipeline.on_envelope(feed(PET, (1, UNKNOWN_STACK)), CLIENT_KEY)
        done.set()
        stop.wait(5.0)

    session = CaptureSession(str(tmp_path / "n.db"), "Brial", None, capture, lambda: NOW,
                             feed=feed_log)
    session.start()
    assert done.wait(5.0)
    return session, feed_log


def test_the_session_shows_the_notice_in_the_logs(tmp_path) -> None:
    session, feed_log = run_unknown_feeding(tmp_path)
    session.stop()
    row = format_log_row(feed_log.entries()[0], lambda item_id: "x")
    assert row[1:] == ("Familier", f"ressource inconnue #{UNKNOWN_STACK}", "ignorée", "reconnecte")


def test_the_snapshot_tells_whether_the_inventory_was_seen(tmp_path) -> None:
    session, _ = run_unknown_feeding(tmp_path)
    assert session.snapshot().pets_inventory_seen is True
    session.stop()
    fresh = CaptureSession(str(tmp_path / "f.db"), "Brial", None, lambda p, i, s: s.wait(0.1), lambda: NOW)
    assert fresh.snapshot().pets_inventory_seen is False
