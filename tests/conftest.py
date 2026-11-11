"""Suite-wide isolation: relative default paths never resolve inside the repository."""

import pytest


@pytest.fixture(autouse=True)
def isolated_working_directory(tmp_path_factory, monkeypatch) -> None:
    """Run every test from an empty temp directory (data/, prices.db, captures/ absent)."""
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path_factory, monkeypatch) -> None:
    """Point the user config file at a temp path: the real %APPDATA% is never touched."""
    config_directory = tmp_path_factory.mktemp("config")
    monkeypatch.setenv("OPENDOFUSDATA_CONFIG", str(config_directory / "config.json"))


@pytest.fixture(scope="session")
def tk_root():
    """One Tk interpreter for the whole run (a second one fails to init on some Windows setups)."""
    tkinter = pytest.importorskip("tkinter")
    customtkinter = pytest.importorskip("customtkinter")
    try:
        interpreter = customtkinter.CTk()
    except tkinter.TclError as error:
        pytest.skip(f"no display available: {error}")
    interpreter.withdraw()
    yield interpreter
    interpreter.destroy()


@pytest.fixture
def root(tk_root):
    """A hidden top-level window for one test."""
    import customtkinter

    window_root = customtkinter.CTkToplevel(tk_root)
    window_root.withdraw()
    yield window_root
    if window_root.winfo_exists():
        window_root.destroy()
