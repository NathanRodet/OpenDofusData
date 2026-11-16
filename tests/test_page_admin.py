"""The Administration tab: generated locally, revoked on the server, present only with the admin secret."""

import threading
from datetime import datetime, timezone

import pytest

pytest.importorskip("customtkinter")

import customtkinter

from opendofusdata.admin_client import RevokeResult
from opendofusdata.admin_keys import make_key
from opendofusdata.admin_registry import AdminRegistry
from opendofusdata.admin_settings import AdminSettings, load_admin_settings
from opendofusdata.capture_session import CaptureSession
from opendofusdata.page_admin import AdminPage
from opendofusdata.window_context import WindowContext
from opendofusdata.window_pages import ADMIN_PAGE, PAGE_NAMES, build_pages
from opendofusdata.window_view import CaptureWindow

SECRET = "A" * 43
URL = "https://sync.exemple.fr"
MOMENT = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(2.0)


def make_context(tmp_path) -> WindowContext:
    session = CaptureSession(str(tmp_path / "old.db"), "Brial", None, idle_capture, lambda: MOMENT)
    return WindowContext(session, tmp_path / "config.json", ["Brial"], lambda item_id: "N/A")


def write_env(tmp_path, secret: str | None = SECRET, url: str | None = URL) -> None:
    lines = ([f"ADMIN_SECRET={secret}"] if secret else []) + ([f"SERVER_URL={url}"] if url else [])
    (tmp_path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


class FakeRevoke:
    def __init__(self, result: RevokeResult = RevokeResult(True, "Clé révoquée")) -> None:
        self.result, self.calls = result, []

    def __call__(self, base_url: str, secret: str, key_id: str, purge: bool = False) -> RevokeResult:
        self.calls.append((base_url, secret, key_id))
        self.purges = [*getattr(self, "purges", []), purge]
        return self.result


def make_page(root, tmp_path, revoke=None, confirm=lambda text: True) -> AdminPage:
    return AdminPage(customtkinter.CTkFrame(root), make_context(tmp_path), AdminSettings(SECRET, URL),
                     revoke or FakeRevoke(), confirm, lambda: MOMENT)


def registry_of(tmp_path) -> AdminRegistry:
    return AdminRegistry(tmp_path / "admin_keys.json", lambda: MOMENT)


def generate(page: AdminPage, label: str) -> None:
    page.label_entry.delete(0, "end")
    page.label_entry.insert(0, label)
    page.generate()


def revoke_and_wait(page: AdminPage, key_id: str) -> None:
    page.revoke(key_id)
    assert page.task.wait(5)
    page.render(None)


def test_settings_need_both_the_secret_and_an_address(tmp_path) -> None:
    env = tmp_path / ".env"
    assert load_admin_settings(env) is None
    write_env(tmp_path, url=None)
    assert load_admin_settings(env) is None
    write_env(tmp_path, secret=None)
    assert load_admin_settings(env) is None
    write_env(tmp_path)
    assert load_admin_settings(env) == AdminSettings(SECRET, URL)


def test_the_page_is_absent_without_the_secret_and_present_with_both(root, tmp_path) -> None:
    context = make_context(tmp_path)
    assert tuple(build_pages(customtkinter.CTkFrame(root), context)) == PAGE_NAMES
    write_env(tmp_path)
    assert tuple(build_pages(customtkinter.CTkFrame(root), context)) == (*PAGE_NAMES, ADMIN_PAGE)


def test_the_window_menu_gets_the_administration_entry_only_with_the_secret(root, tmp_path) -> None:
    write_env(tmp_path)
    window = CaptureWindow(root, make_context(tmp_path))
    assert ADMIN_PAGE in window.pages and ADMIN_PAGE in window.menu_buttons
    window.show_page(ADMIN_PAGE)
    assert window.current_page == ADMIN_PAGE


def test_generating_adds_a_row_without_any_network_call(root, tmp_path) -> None:
    revoke = FakeRevoke()
    page = make_page(root, tmp_path, revoke)
    generate(page, "Joueur Un")
    entries = registry_of(tmp_path).entries()
    assert [entry.label for entry in entries] == ["Joueur Un"] and revoke.calls == []
    assert page.visible_entries == entries
    assert page.new_key_label.cget("text") == make_key(SECRET, entries[0].key_id)


def test_the_new_key_can_be_copied(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    generate(page, "Joueur Un")
    page.copy_new_key()
    assert root.clipboard_get() == make_key(SECRET, registry_of(tmp_path).entries()[0].key_id)


def test_copying_an_existing_row_recomputes_the_same_key(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    generate(page, "Joueur Un")
    key_id = registry_of(tmp_path).entries()[0].key_id
    page.hide_new_key()
    page.copy_key(key_id)
    assert root.clipboard_get() == make_key(SECRET, key_id)


@pytest.mark.parametrize("label", ["", "   ", "A" * 61, "a\nb"])
def test_an_unusable_label_is_refused_with_a_message(root, tmp_path, label: str) -> None:
    page = make_page(root, tmp_path)
    generate(page, label)
    assert registry_of(tmp_path).entries() == [] and page.message_label.cget("text") != ""


def test_a_duplicate_active_label_is_refused(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    generate(page, "Joueur")
    generate(page, "joueur")
    assert len(registry_of(tmp_path).entries()) == 1
    assert "déjà" in page.message_label.cget("text")


def test_the_list_is_filled_from_the_registry_and_marks_revoked_keys(root, tmp_path) -> None:
    store = registry_of(tmp_path)
    store.add("Un", "AAAAAAAAAAA")
    store.add("Deux", "BBBBBBBBBBB")
    store.mark_revoked("BBBBBBBBBBB")
    page = make_page(root, tmp_path)
    assert [entry.label for entry in page.visible_entries] == ["Un", "Deux"]
    assert "révoquée" in page.row_status("BBBBBBBBBBB").lower()
    assert "révoquée" not in page.row_status("AAAAAAAAAAA").lower()


def test_revoking_needs_confirmation(root, tmp_path) -> None:
    revoke = FakeRevoke()
    page = make_page(root, tmp_path, revoke, confirm=lambda text: False)
    generate(page, "Joueur Un")
    page.revoke(registry_of(tmp_path).entries()[0].key_id)
    assert revoke.calls == [] and registry_of(tmp_path).entries()[0].revoked_at is None


def test_a_confirmed_revocation_calls_the_server_then_marks_the_row(root, tmp_path) -> None:
    revoke = FakeRevoke()
    page = make_page(root, tmp_path, revoke)
    generate(page, "Joueur Un")
    key_id = registry_of(tmp_path).entries()[0].key_id
    revoke_and_wait(page, key_id)
    assert revoke.calls == [(URL, SECRET, key_id)]
    assert registry_of(tmp_path).entries()[0].revoked_at is not None
    assert "révoquée" in page.row_status(key_id).lower()


def test_a_failed_revocation_leaves_the_registry_unchanged_and_shows_the_error(root, tmp_path) -> None:
    page = make_page(root, tmp_path, FakeRevoke(RevokeResult(False, "Serveur injoignable")))
    generate(page, "Joueur Un")
    key_id = registry_of(tmp_path).entries()[0].key_id
    revoke_and_wait(page, key_id)
    assert registry_of(tmp_path).entries()[0].revoked_at is None
    assert page.message_label.cget("text") == "Serveur injoignable"


def test_nothing_is_sent_when_the_page_is_built_or_rendered(root, tmp_path) -> None:
    revoke = FakeRevoke()
    registry_of(tmp_path).add("Un", "AAAAAAAAAAA")
    page = make_page(root, tmp_path, revoke)
    page.render(None)
    assert revoke.calls == []


def test_a_second_revocation_while_one_runs_is_ignored_and_never_marks_the_wrong_row(root, tmp_path) -> None:
    release, started, calls = threading.Event(), threading.Event(), []

    def slow_revoke(base_url: str, secret: str, key_id: str) -> RevokeResult:
        calls.append(key_id)
        started.set()
        release.wait(5)
        return RevokeResult(True, "Clé révoquée")

    page = make_page(root, tmp_path, slow_revoke)
    generate(page, "A")
    generate(page, "B")
    ids = {entry.label: entry.key_id for entry in registry_of(tmp_path).entries()}
    page.revoke(ids["A"])
    assert started.wait(5)
    page.revoke(ids["B"])
    release.set()
    assert page.task.wait(5)
    page.render(None)
    revoked = {entry.label: entry.revoked_at is not None for entry in registry_of(tmp_path).entries()}
    assert calls == [ids["A"]]
    assert revoked == {"A": True, "B": False}


def purge_and_wait(page: AdminPage, key_id: str) -> None:
    page.revoke_and_purge(key_id)
    assert page.task.wait(5)
    page.render(None)


def test_page_offers_both_revocation_choices_with_their_own_confirmation(root, tmp_path) -> None:
    texts: list[str] = []
    revoke = FakeRevoke()
    page = make_page(root, tmp_path, revoke, confirm=lambda text: texts.append(text) or False)
    generate(page, "Joueur Un")
    key_id = registry_of(tmp_path).entries()[0].key_id
    page.revoke(key_id)
    page.revoke_and_purge(key_id)
    assert len(texts) == 2 and texts[0] != texts[1]
    assert "supprim" in texts[1].lower() and "supprim" not in texts[0].lower()
    assert "Joueur Un" in texts[0] and "Joueur Un" in texts[1]


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def test_rows_have_a_revoke_and_purge_button(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    generate(page, "Joueur Un")
    labels = [child.cget("text") for child in descendants(page.rows) if isinstance(child, customtkinter.CTkButton)]
    assert "Révoquer" in labels and "Révoquer et purger" in labels


def test_revoke_with_purge_asks_the_server_for_the_purge_and_marks_the_row_after_the_answer(root, tmp_path) -> None:
    revoke = FakeRevoke(RevokeResult(True, "Clé révoquée, 3 relevé(s) supprimé(s)"))
    page = make_page(root, tmp_path, revoke)
    generate(page, "Joueur Un")
    key_id = registry_of(tmp_path).entries()[0].key_id
    purge_and_wait(page, key_id)
    assert revoke.calls == [(URL, SECRET, key_id)] and revoke.purges == [True]
    assert registry_of(tmp_path).entries()[0].revoked_at is not None
    assert page.message_label.cget("text") == "Clé révoquée, 3 relevé(s) supprimé(s)"


def test_plain_revocation_does_not_ask_for_the_purge(root, tmp_path) -> None:
    revoke = FakeRevoke()
    page = make_page(root, tmp_path, revoke)
    generate(page, "Joueur Un")
    revoke_and_wait(page, registry_of(tmp_path).entries()[0].key_id)
    assert revoke.purges == [False]


def test_a_failed_purge_revocation_leaves_the_registry_unchanged(root, tmp_path) -> None:
    page = make_page(root, tmp_path, FakeRevoke(RevokeResult(False, "Serveur injoignable")))
    generate(page, "Joueur Un")
    key_id = registry_of(tmp_path).entries()[0].key_id
    purge_and_wait(page, key_id)
    assert registry_of(tmp_path).entries()[0].revoked_at is None


def test_cancelled_purge_confirmation_sends_nothing(root, tmp_path) -> None:
    revoke = FakeRevoke()
    page = make_page(root, tmp_path, revoke, confirm=lambda text: False)
    generate(page, "Joueur Un")
    page.revoke_and_purge(registry_of(tmp_path).entries()[0].key_id)
    assert revoke.calls == [] and registry_of(tmp_path).entries()[0].revoked_at is None
