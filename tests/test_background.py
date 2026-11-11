"""Tests of the background task helper (one worker thread, observable state)."""

import threading

from opendofusdata.background import BackgroundTask, TaskState

WAIT_SECONDS = 5.0


def wait_until_finished(task: BackgroundTask) -> None:
    assert task.wait(WAIT_SECONDS)


def test_a_new_task_is_idle() -> None:
    task = BackgroundTask(lambda: "x", (ValueError,))
    assert task.snapshot().state is TaskState.IDLE and task.snapshot().message == ""


def test_a_finished_task_keeps_the_result_message() -> None:
    task = BackgroundTask(lambda: "12 objets", (ValueError,))
    assert task.start() is True
    wait_until_finished(task)
    assert (task.snapshot().state, task.snapshot().message) == (TaskState.DONE, "12 objets")


def test_an_expected_failure_becomes_a_failed_state_with_its_message() -> None:
    def work() -> str:
        raise ValueError("réseau coupé")

    task = BackgroundTask(work, (ValueError,))
    task.start()
    wait_until_finished(task)
    assert (task.snapshot().state, task.snapshot().message) == (TaskState.FAILED, "réseau coupé")


def test_an_unexpected_failure_is_logged_and_reported_generically(caplog) -> None:
    def work() -> str:
        raise KeyError("boom")

    task = BackgroundTask(work, (ValueError,))
    task.start()
    wait_until_finished(task)
    assert task.snapshot().state is TaskState.FAILED
    assert "erreur inattendue" in task.snapshot().message
    assert "boom" in caplog.text


def test_start_while_running_does_nothing() -> None:
    release = threading.Event()
    calls: list[int] = []

    def work() -> str:
        calls.append(1)
        release.wait(WAIT_SECONDS)
        return "ok"

    task = BackgroundTask(work, (ValueError,))
    assert task.start() is True
    assert task.snapshot().state is TaskState.RUNNING
    assert task.start() is False
    release.set()
    wait_until_finished(task)
    assert calls == [1]


def test_a_finished_task_can_be_started_again() -> None:
    task = BackgroundTask(lambda: "ok", (ValueError,))
    task.start()
    wait_until_finished(task)
    assert task.start() is True
    wait_until_finished(task)
    assert task.snapshot().state is TaskState.DONE
