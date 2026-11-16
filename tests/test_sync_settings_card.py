"""The "Synchronisation" card of the Réglages: key field, save and connection test (no network at all)."""

import json
import threading
from datetime import datetime, timezone

import pytest

pytest.importorskip("customtkinter")

import customtkinter

from opendofusdata.capture_session import CaptureSession
from opendofusdata.page_settings import SettingsPage
from opendofusdata.sync_client import ConnectionResult
from opendofusdata.sync_key import SYNC_KEY_CONFIG
from opendofusdata.sync_settings_card import MASK_CHARACTER, SyncSettingsCard
from opendofusdata.window_context import WindowContext

KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"
URL = "https://sync.exemple.fr"
MOMENT = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(2.0)


def make_context(tmp_path) -> WindowContext:
    session = CaptureSession(str(tmp_path / "old.db"), "Brial", None, idle_capture, lambda: MOMENT)
    return WindowContext(session, tmp_path / "config.json", ["Brial"], lambda item_id: "N/A")


class FakeCheck:
    def __init__(self, result: ConnectionResult = ConnectionResult(True, "Connexion réussie")) -> None:
        self.result, self.calls = result, []

    def __call__(self, base_url: str, key: str) -> ConnectionResult:
        self.calls.append((base_url, key))
        return self.result


def make_card(root, tmp_path, check=None, url=URL) -> SyncSettingsCard:
    return SyncSettingsCard(customtkinter.CTkFrame(root), make_context(tmp_path), check or FakeCheck(), url)


def saved(tmp_path) -> dict:
    return json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))


def run_test(card: SyncSettingsCard) -> None:
    card.test()
    assert card.task.wait(5)
    card.render()


def test_the_key_field_is_masked_by_default_and_revealed_by_the_box(root, tmp_path) -> None:
    card = make_card(root, tmp_path)
    assert card.entry.cget("show") == MASK_CHARACTER
    card.show_box.select()
    card.toggle_visibility()
    assert card.entry.cget("show") == ""
    card.show_box.deselect()
    card.toggle_visibility()
    assert card.entry.cget("show") == MASK_CHARACTER


def test_an_existing_key_is_loaded_into_the_masked_field(root, tmp_path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({SYNC_KEY_CONFIG: KEY}), encoding="utf-8")
    card = make_card(root, tmp_path)
    assert card.entry.get() == KEY and card.entry.cget("show") == MASK_CHARACTER


def test_saving_a_valid_key_stores_it_cleaned(root, tmp_path) -> None:
    card = make_card(root, tmp_path)
    card.entry.insert(0, f"  {KEY}\n")
    card.save()
    assert saved(tmp_path)[SYNC_KEY_CONFIG] == KEY
    assert card.status_label.cget("text") == "Clé enregistrée."


def test_saving_an_invalid_key_shows_an_error_and_writes_nothing(root, tmp_path) -> None:
    card = make_card(root, tmp_path)
    card.entry.insert(0, "pas une clé")
    card.save()
    assert not (tmp_path / "config.json").exists()
    assert "format" in card.status_label.cget("text").lower()


def test_saving_an_empty_field_removes_the_key(root, tmp_path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({SYNC_KEY_CONFIG: KEY, "server": "Brial"}), encoding="utf-8")
    card = make_card(root, tmp_path)
    card.entry.delete(0, "end")
    card.save()
    assert saved(tmp_path)["server"] == "Brial" and SYNC_KEY_CONFIG not in saved(tmp_path)
    assert card.status_label.cget("text") == "Clé retirée."


def test_the_connection_test_shows_the_success(root, tmp_path) -> None:
    check = FakeCheck()
    card = make_card(root, tmp_path, check)
    card.entry.insert(0, KEY)
    run_test(card)
    assert card.status_label.cget("text") == "Connexion réussie"
    assert check.calls == [(URL, KEY)]


def test_a_failed_connection_test_shows_the_message(root, tmp_path) -> None:
    card = make_card(root, tmp_path, FakeCheck(ConnectionResult(False, "Clé refusée ou révoquée")))
    card.entry.insert(0, KEY)
    run_test(card)
    assert card.status_label.cget("text") == "Clé refusée ou révoquée"


def test_the_test_uses_the_field_even_when_it_was_not_saved(root, tmp_path) -> None:
    check = FakeCheck()
    card = make_card(root, tmp_path, check)
    card.entry.insert(0, f" {KEY} ")
    run_test(card)
    assert check.calls == [(URL, KEY)] and not (tmp_path / "config.json").exists()


@pytest.mark.parametrize("text", ["", "pas une clé"])
def test_a_missing_or_malformed_key_never_reaches_the_network(root, tmp_path, text: str) -> None:
    check = FakeCheck()
    card = make_card(root, tmp_path, check)
    card.entry.insert(0, text)
    card.test()
    assert check.calls == []
    assert card.status_label.cget("text") != ""


def test_the_test_button_is_disabled_without_a_server_address(root, tmp_path) -> None:
    card = make_card(root, tmp_path, url=None)
    assert card.test_button.cget("state") == "disabled"
    assert "non configuré" in card.status_label.cget("text")


def test_the_test_button_is_enabled_with_a_server_address(root, tmp_path) -> None:
    assert make_card(root, tmp_path).test_button.cget("state") == "normal"


def test_nothing_is_sent_when_the_card_is_built_or_rendered(root, tmp_path) -> None:
    check = FakeCheck()
    (tmp_path / "config.json").write_text(json.dumps({SYNC_KEY_CONFIG: KEY}), encoding="utf-8")
    card = make_card(root, tmp_path, check)
    card.render()
    assert check.calls == []


def test_the_settings_page_has_the_card_and_the_about_text_mentions_the_test(root, tmp_path) -> None:
    page = SettingsPage(root, make_context(tmp_path), lambda current: None)
    assert isinstance(page.sync_card, SyncSettingsCard)
    assert "test de connexion" in page.about_card.summary_label.cget("text").lower()


def test_card_has_two_unchecked_send_and_receive_boxes(root, tmp_path) -> None:
    card = make_card(root, tmp_path)
    assert card.send_box.get() == 0
    assert card.receive_box.get() == 0


def test_saved_settings_are_shown_in_the_boxes(root, tmp_path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"sync_send": True, "sync_receive": True}), encoding="utf-8")
    card = make_card(root, tmp_path)
    assert card.send_box.get() == 1
    assert card.receive_box.get() == 1


def test_boxes_are_disabled_without_key_or_server(root, tmp_path) -> None:
    assert make_card(root, tmp_path, url=None).send_box.cget("state") == "disabled"
    card = make_card(root, tmp_path)
    assert card.send_box.cget("state") == "disabled" and card.receive_box.cget("state") == "disabled"
    card.entry.insert(0, KEY)
    card.save()
    card.render()
    assert card.send_box.cget("state") == "normal" and card.receive_box.cget("state") == "normal"


def test_ticking_a_box_saves_the_setting_and_keeps_the_other_settings(root, tmp_path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({SYNC_KEY_CONFIG: KEY, "server": "Brial"}), encoding="utf-8")
    card = make_card(root, tmp_path)
    card.send_box.select()
    card.toggle_send()
    assert saved(tmp_path)["sync_send"] is True and saved(tmp_path)["server"] == "Brial"
    card.receive_box.select()
    card.toggle_receive()
    assert saved(tmp_path)["sync_receive"] is True
    card.send_box.deselect()
    card.toggle_send()
    assert saved(tmp_path)["sync_send"] is False and saved(tmp_path)["sync_receive"] is True


def test_card_shows_the_worker_status(root, tmp_path) -> None:
    status = ["Synchronisation terminée"]
    card = SyncSettingsCard(customtkinter.CTkFrame(root), make_context(tmp_path), FakeCheck(), URL,
                            lambda: status[0])
    card.render()
    assert "Synchronisation terminée" in card.sync_status_label.cget("text")
    status[0] = "Serveur injoignable"
    card.render()
    assert "Serveur injoignable" in card.sync_status_label.cget("text")
