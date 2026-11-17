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


def test_the_card_has_no_send_or_receive_choice_any_more(root, tmp_path) -> None:
    card = make_card(root, tmp_path)
    assert not hasattr(card, "send_box") and not hasattr(card, "receive_box")


def test_the_note_says_that_a_saved_key_turns_sharing_on(root, tmp_path) -> None:
    from opendofusdata.sync_settings_card import NOTE

    assert "clé" in NOTE and "envoy" in NOTE and "récup" in NOTE


def test_card_shows_the_worker_status(root, tmp_path) -> None:
    status = ["Synchronisation terminée"]
    card = SyncSettingsCard(customtkinter.CTkFrame(root), make_context(tmp_path), FakeCheck(), URL,
                            lambda: status[0])
    card.render()
    assert "Synchronisation terminée" in card.sync_status_label.cget("text")
    status[0] = "Serveur injoignable"
    card.render()
    assert "Serveur injoignable" in card.sync_status_label.cget("text")


def test_card_shows_the_counters_under_the_status_and_follows_new_data(root, tmp_path, monkeypatch) -> None:
    from opendofusdata import sync_settings_card
    from opendofusdata.storage import PriceStore

    connection = PriceStore(str(tmp_path / "old.db")).connection
    card = SyncSettingsCard(customtkinter.CTkFrame(root), make_context(tmp_path), FakeCheck(), URL,
                            lambda: "Synchronisation terminée")
    card.render()
    assert "Reçus des autres joueurs : 0" in card.sync_status_label.cget("text")
    connection.execute("INSERT INTO lot_prices (item_id, server, lot_size, price, captured_at, origin) "
                       "VALUES (1, 'Brial', 1, 10, '2026-11-16T10:00:00Z', 'remote')")
    connection.commit()
    monkeypatch.setattr(sync_settings_card, "COUNTS_REFRESH_SECONDS", 0.0)
    card.render()
    assert "Reçus des autres joueurs : 1" in card.sync_status_label.cget("text")


def test_the_address_field_shows_the_address_in_use(root, tmp_path) -> None:
    card = make_card(root, tmp_path)
    assert card.address_entry.get() == "sync.exemple.fr"  # the domain alone: https is added by the application


def test_saving_a_new_address_stores_it_and_enables_the_test(root, tmp_path) -> None:
    card = make_card(root, tmp_path, url=None)
    card.render()
    assert card.test_button.cget("state") == "disabled"
    card.address_entry.insert(0, " nouveau.exemple.fr ")
    card.entry.insert(0, KEY)
    card.save()
    assert saved(tmp_path)["sync_server_url"] == "https://nouveau.exemple.fr"
    card.render()
    assert card.test_button.cget("state") == "normal"


def test_a_bad_address_is_refused_and_not_stored(root, tmp_path) -> None:
    card = make_card(root, tmp_path, url=None)
    card.address_entry.insert(0, "http://pas-securise.fr")
    card.save()
    assert "sync_server_url" not in saved(tmp_path) if (tmp_path / "config.json").exists() else True
    assert "Domaine invalide" in card.status_label.cget("text")


def test_the_connection_test_uses_the_typed_address_even_when_unsaved(root, tmp_path) -> None:
    check = FakeCheck()
    card = make_card(root, tmp_path, check, url=None)
    card.address_entry.insert(0, "essai.exemple.fr")
    card.entry.insert(0, KEY)
    run_test(card)
    assert check.calls == [("https://essai.exemple.fr", KEY)]


def test_the_test_button_is_off_without_any_address(root, tmp_path) -> None:
    card = make_card(root, tmp_path, url=None)
    card.render()
    assert card.test_button.cget("state") == "disabled"
