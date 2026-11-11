"""Update controller: background check, availability and one-click install (no GUI dependency)."""

import threading
from collections.abc import Callable

from opendofusdata.app_links import RELEASES_API_URL
from opendofusdata.background import BackgroundTask, TaskSnapshot
from opendofusdata.names_fetch import FetchJson, NamesFetchError, TransientFetchError
from opendofusdata.update_download import UpdateError
from opendofusdata.updates import UpdateInfo, find_update

AVAILABLE_MESSAGE = "Version {version} disponible."
UP_TO_DATE_MESSAGE = "Tu as la dernière version ({version})."
RESTARTING_MESSAGE = "Redémarrage..."
FAILURES = (NamesFetchError, TransientFetchError, UpdateError)
Check = Callable[[], UpdateInfo | None]
Install = Callable[[UpdateInfo], None]


def check_for_update(current_version: str, fetch: FetchJson) -> UpdateInfo | None:
    """Ask GitHub for the latest release (one anonymous GET); None when up to date."""
    return find_update(fetch(RELEASES_API_URL), current_version)


class UpdateController:
    """Never updates by itself: it checks, tells what exists, and installs only on request."""

    def __init__(self, current_version: str, enabled: bool, check: Check, install: Install,
                 can_self_update: bool) -> None:
        self._version, self.enabled, self.can_self_update = current_version, enabled, can_self_update
        self._check, self._install = check, install
        self._lock = threading.Lock()
        self._info: UpdateInfo | None = None
        self._restart_requested = False
        self._check_task = BackgroundTask(self._run_check, FAILURES)
        self._install_task = BackgroundTask(self._run_install, FAILURES)

    @classmethod
    def inert(cls) -> "UpdateController":
        """A controller that does nothing (tests, source checkouts without a release channel)."""
        return cls("0.0.0", False, lambda: None, lambda info: None, False)

    def start_check(self, manual: bool = False) -> bool:
        """Start a check in the background when enabled (or asked for by the player)."""
        return (self.enabled or manual) and self._check_task.start()

    def _run_check(self) -> str:
        info = self._check()
        with self._lock:
            self._info = info
        if info is None:
            return UP_TO_DATE_MESSAGE.format(version=self._version)
        return AVAILABLE_MESSAGE.format(version=info.version)

    def available(self) -> UpdateInfo | None:
        """The newer release found by the last check, if any."""
        with self._lock:
            return self._info

    def check_snapshot(self) -> TaskSnapshot:
        """State and message of the last check."""
        return self._check_task.snapshot()

    def wait_for_check(self, timeout: float) -> bool:
        """Wait for a running check (tests)."""
        return self._check_task.wait(timeout)

    def start_install(self) -> bool:
        """Download, verify and schedule the replacement of the running program."""
        info = self.available()
        if info is None or not info.can_install or not self.can_self_update:
            return False
        return self._install_task.start()

    def _run_install(self) -> str:
        info = self.available()
        self._install(info)
        with self._lock:
            self._restart_requested = True
        return RESTARTING_MESSAGE

    def install_snapshot(self) -> TaskSnapshot:
        """State and message of the install."""
        return self._install_task.snapshot()

    def wait_for_install(self, timeout: float) -> bool:
        """Wait for a running install (tests)."""
        return self._install_task.wait(timeout)

    def take_restart_request(self) -> bool:
        """True once after a successful install: the window must now close."""
        with self._lock:
            requested, self._restart_requested = self._restart_requested, False
            return requested
