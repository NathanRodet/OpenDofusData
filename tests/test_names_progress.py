"""The progress of the reference data download."""

from opendofusdata.names_progress import DownloadProgress


def test_nothing_is_shown_before_a_page_count_is_reported() -> None:
    progress = DownloadProgress()
    progress.report("Téléchargement des objets...")
    assert progress.pages() == "" and progress.detail() == ""


def test_the_last_page_count_is_kept_and_reset_forgets_it() -> None:
    progress = DownloadProgress()
    progress.report("  items : 3/45 pages téléchargées...")
    progress.report("  recipes : 7/9 pages téléchargées...")
    assert progress.pages() == "7/9" and progress.detail() == "recipes 7/9 pages"
    progress.reset()
    assert progress.pages() == ""
