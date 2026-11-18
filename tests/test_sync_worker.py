"""The background worker: one round per interval with the current options, back off on errors, stop on a refusal."""

import threading
import time

import pytest

from opendofusdata.sync_engine import DONE_MESSAGE, SyncOptions, SyncOutcome
from opendofusdata.sync_worker import MAX_BACKOFF_SECONDS, SYNC_INTERVAL_SECONDS, SyncWorker

OPTIONS = SyncOptions("https://sync.exemple.fr", "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI", True, True)
WAIT = 5.0


def wait_for(condition, timeout: float = WAIT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.005)
    return False


class Rounds:
    """A fake engine: answers from a list (the last answer repeats) and records each call."""

    def __init__(self, *outcomes: SyncOutcome) -> None:
        self.outcomes, self.calls, self.stamps = list(outcomes), 0, []

    def __call__(self, connection, options) -> SyncOutcome:
        self.calls += 1
        self.stamps.append(time.monotonic())
        return self.outcomes[min(self.calls, len(self.outcomes)) - 1]


OK = SyncOutcome(0, 0, False, DONE_MESSAGE)
DOWN = SyncOutcome(0, 0, False, "Serveur injoignable")
REFUSED = SyncOutcome(0, 0, True, "Clé refusée ou révoquée")


def make_worker(tmp_path, rounds: Rounds, options=OPTIONS, interval: float = 0.01) -> SyncWorker:
    return SyncWorker(lambda: str(tmp_path / "prices.db"), lambda: options, interval, rounds)


def test_constants() -> None:
    assert (SYNC_INTERVAL_SECONDS, MAX_BACKOFF_SECONDS) == (30, 3600)


def test_worker_runs_rounds_with_the_current_options(tmp_path) -> None:
    rounds = Rounds(OK)
    worker = make_worker(tmp_path, rounds)
    worker.start()
    assert wait_for(lambda: rounds.calls >= 3)
    worker.stop()
    assert worker.status() == DONE_MESSAGE


def test_worker_does_nothing_when_options_are_none(tmp_path) -> None:
    rounds = Rounds(OK)
    worker = make_worker(tmp_path, rounds, options=None)
    worker.start()
    time.sleep(0.1)
    worker.stop()
    assert rounds.calls == 0 and worker.status() == ""
    assert not (tmp_path / "prices.db").exists()


def test_a_refused_key_pauses_the_rounds_until_the_player_saves_another_key(tmp_path) -> None:
    current = [OPTIONS]
    rounds = Rounds(REFUSED, OK)
    worker = SyncWorker(lambda: str(tmp_path / "prices.db"), lambda: current[0], 0.01, rounds)
    worker.start()
    assert wait_for(lambda: rounds.calls == 1)
    time.sleep(0.1)
    assert rounds.calls == 1 and worker.status() == "Clé refusée ou révoquée"  # paused, thread still alive
    assert worker.is_running()
    current[0] = OPTIONS._replace(key="odk1.BBBBBBBBBBB.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI")
    assert wait_for(lambda: rounds.calls >= 2)
    worker.stop()
    assert worker.status() == DONE_MESSAGE


def test_worker_keeps_running_through_errors_and_recovery(tmp_path) -> None:
    rounds = Rounds(DOWN, DOWN, DOWN, OK, OK, OK)
    worker = make_worker(tmp_path, rounds, interval=0.005)
    worker.start()
    assert wait_for(lambda: rounds.calls >= 6)
    worker.stop()
    assert worker.status() == DONE_MESSAGE


def test_backoff_doubles_while_the_server_is_down_and_resets_after_a_success(tmp_path) -> None:
    worker = make_worker(tmp_path, Rounds(OK), interval=10.0)
    assert [worker.next_delay(DOWN) for _ in range(3)] == [20.0, 40.0, 80.0]
    assert worker.next_delay(OK) == 10.0
    assert worker.next_delay(DOWN) == 20.0


def test_backoff_is_capped(tmp_path) -> None:
    worker = make_worker(tmp_path, Rounds(OK), interval=1000.0)
    delays = [worker.next_delay(DOWN) for _ in range(10)]
    assert delays[-1] == MAX_BACKOFF_SECONDS
    assert max(delays) <= MAX_BACKOFF_SECONDS


def test_an_engine_crash_is_reported_and_does_not_kill_the_worker(tmp_path) -> None:
    calls = []

    def crashing(connection, options) -> SyncOutcome:
        calls.append(1)
        raise RuntimeError("boom")

    worker = SyncWorker(lambda: str(tmp_path / "prices.db"), lambda: OPTIONS, 0.01, crashing)
    worker.start()
    assert wait_for(lambda: len(calls) >= 2)
    worker.stop()
    assert "inattendue" in worker.status()


def test_stop_ends_the_thread_quickly(tmp_path) -> None:
    worker = make_worker(tmp_path, Rounds(OK), interval=3600.0)
    worker.start()
    started = time.monotonic()
    worker.stop()
    assert time.monotonic() - started < 3.0 and not worker.is_running()


def test_the_summary_follows_the_round(tmp_path) -> None:
    release, entered = threading.Event(), threading.Event()

    def slow_round(connection, options) -> SyncOutcome:
        entered.set()
        release.wait(WAIT)
        return SyncOutcome(2, 14, False, DONE_MESSAGE)

    worker = make_worker(tmp_path, slow_round, interval=60.0)
    assert worker.summary() == "pas encore lancée"
    worker.start()
    assert entered.wait(WAIT) and worker.summary() == "en cours..."
    release.set()
    assert wait_for(lambda: worker.summary() == "à jour, 14 reçus")
    worker.stop()


def test_the_summary_says_when_sharing_is_off_or_a_round_failed(tmp_path) -> None:
    off = make_worker(tmp_path, Rounds(OK), options=None)
    off.start()
    assert wait_for(lambda: off.summary() == "désactivée")
    off.stop()
    failing = make_worker(tmp_path, Rounds(DOWN), interval=60.0)
    failing.start()
    assert wait_for(lambda: failing.summary() == "échec, voir Réglages")
    failing.stop()
    refused = make_worker(tmp_path, Rounds(REFUSED), interval=60.0)
    refused.start()
    assert wait_for(lambda: refused.summary() == "clé refusée")
    refused.stop()


def test_a_wake_up_runs_the_next_round_without_waiting_for_the_interval(tmp_path) -> None:
    rounds = Rounds(OK)
    worker = make_worker(tmp_path, rounds, interval=1000.0)
    worker.start()
    assert wait_for(lambda: rounds.calls >= 1)
    worker.wake()
    assert wait_for(lambda: rounds.calls >= 2)
    worker.stop()


def test_the_interval_of_the_options_replaces_the_default_one(tmp_path) -> None:
    from opendofusdata.sync_engine import SyncOptions

    worker = make_worker(tmp_path, Rounds(OK), options=SyncOptions("https://s.example.fr", "odk1.k", True, True, 45.0),
                         interval=1000.0)
    assert worker._round() == 45.0
