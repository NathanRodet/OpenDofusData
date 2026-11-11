"""Install an update: download and verify it next to the running program, then schedule the swap."""

import sys
from collections.abc import Callable
from pathlib import Path

from opendofusdata.update_apply import launch_replacement
from opendofusdata.update_download import UpdateError, download_update
from opendofusdata.updates import UpdateInfo

WRITE_FAILED_MESSAGE = "Impossible d'écrire dans {folder} ({error}). Télécharge la version à la main."
Download = Callable[[UpdateInfo, Path], Path]
Launch = Callable[[Path], None]


def install_update(
    info: UpdateInfo, folder: Path | None = None, download: Download = download_update,
    launch: Launch = launch_replacement,
) -> None:
    """Download the verified executable beside the running one, then start the replacement helper."""
    target_folder = folder or Path(sys.executable).parent
    try:
        new_path = download(info, target_folder)
    except OSError as error:
        raise UpdateError(WRITE_FAILED_MESSAGE.format(folder=target_folder, error=error)) from error
    launch(new_path)
