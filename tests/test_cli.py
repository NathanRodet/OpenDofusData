"""Tests for the run and read commands of the CLI."""

import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from opendofusdata import cli
from opendofusdata.capture import CaptureAborted, PacketPipeline
from opendofusdata.storage import LotPrice, MarketStats, PriceStore
from tests.envelopes import FLOW_KEY, lot_envelope

CAPTURE_MOMENT = datetime(2026, 11, 10, 10, 29, 17, tzinfo=timezone.utc)
CAPTURED_AT = "2026-11-10T10:29:17Z"
READ_COMMANDS = (["prices"], ["history", "307", "--lot", "1"], ["stats", "307"], ["export-csv", "--output", "x.csv"])


def seed(path: Path) -> None:
    store = PriceStore(str(path))
    try:
        store.save_lot_price(LotPrice(307, "Ilyzaelle", 1, 700, "2026-11-09T10:00:00Z"))
        store.save_lot_price(LotPrice(307, "Ilyzaelle", 1, 750, CAPTURED_AT))
        store.save_lot_price(LotPrice(307, "Ilyzaelle", 10, 5868, CAPTURED_AT))
        store.save_lot_price(LotPrice(999, "Ilyzaelle", 1, 42, CAPTURED_AT))
        store.save_market_stats(MarketStats(307, "Ilyzaelle", "24h", [], 100, 110, 7,
                                            CAPTURED_AT, "2026-11-10T09:00:00Z", CAPTURED_AT))
        store.save_market_stats(MarketStats(307, "Ilyzaelle", "7d", [], 200, 210, 70,
                                            CAPTURED_AT, "2026-11-10T09:00:00Z", CAPTURED_AT))
    finally:
        store.close()


def no_capture(pipeline: PacketPipeline, interface: str | None) -> None:
    return None


def run_cli(argv: list[str], capture=no_capture) -> int:
    return cli.run(argv, capture, lambda: CAPTURE_MOMENT)


def test_cli_prices_lists_latest_prices(tmp_path: Path, capsys) -> None:
    seed(tmp_path / "p.db")
    assert run_cli(["prices", "--db", str(tmp_path / "p.db")]) == 0
    output = capsys.readouterr().out
    assert "750" in output and "700" not in output and "999" in output
    assert "captured_at" in output and CAPTURED_AT in output
    assert run_cli(["prices", "--db", str(tmp_path / "p.db"), "--item", "999"]) == 0
    assert "5868" not in capsys.readouterr().out


def test_cli_prices_on_empty_database_says_so(tmp_path: Path, capsys) -> None:
    PriceStore(str(tmp_path / "p.db")).close()
    assert run_cli(["prices", "--db", str(tmp_path / "p.db")]) == 0
    assert "Aucun prix enregistré" in capsys.readouterr().out


def test_cli_history_filters_by_item_and_lot(tmp_path: Path, capsys) -> None:
    seed(tmp_path / "p.db")
    assert run_cli(["history", "307", "--lot", "1", "--db", str(tmp_path / "p.db")]) == 0
    output = capsys.readouterr().out
    assert "700" in output and "750" in output and "5868" not in output and "42" not in output


def test_cli_history_rejects_unknown_lot_size(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        run_cli(["history", "307", "--lot", "5", "--db", str(tmp_path / "p.db")])


def test_cli_stats_prints_requested_period(tmp_path: Path, capsys) -> None:
    seed(tmp_path / "p.db")
    assert run_cli(["stats", "307", "--period", "7d", "--db", str(tmp_path / "p.db")]) == 0
    output = capsys.readouterr().out
    assert "7d" in output and "200" in output and "24h" not in output
    assert run_cli(["stats", "307", "--db", str(tmp_path / "p.db")]) == 0
    assert "24h" in capsys.readouterr().out


def test_cli_stats_without_data_says_so(tmp_path: Path, capsys) -> None:
    seed(tmp_path / "p.db")
    assert run_cli(["stats", "12345", "--db", str(tmp_path / "p.db")]) == 0
    assert "Aucune statistique" in capsys.readouterr().out


def test_cli_export_csv_creates_file(tmp_path: Path) -> None:
    seed(tmp_path / "p.db")
    output = tmp_path / "out" / "prices.csv"
    assert run_cli(["export-csv", "--output", str(output), "--db", str(tmp_path / "p.db")]) == 0
    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["item_id", "item_name", "item_category", "server", "lot_size", "price", "captured_at"]
    assert len(rows) == 1 + 4


@pytest.mark.parametrize("command", READ_COMMANDS)
def test_read_commands_do_not_create_a_missing_database(tmp_path: Path, capsys, command) -> None:
    missing = tmp_path / "missing.db"
    assert run_cli([*command, "--db", str(missing)]) != 0
    assert not missing.exists()
    assert str(missing) in capsys.readouterr().err


def test_cli_run_stops_cleanly_on_keyboard_interrupt(tmp_path: Path, capsys) -> None:
    database = tmp_path / "p.db"

    def fake_capture(pipeline: PacketPipeline, interface: str | None) -> None:
        pipeline.on_envelope(lot_envelope(), FLOW_KEY)
        raise KeyboardInterrupt

    argv = ["run", "--db", str(database), "--server", "Ilyzaelle"]
    assert run_cli(argv, fake_capture) == 0
    output = capsys.readouterr().out
    assert str(database) in output and "Ilyzaelle" in output
    assert "Arrêt. 4 messages décodés." in output
    store = PriceStore(str(database))
    try:
        assert [lot.captured_at for lot in store.latest_prices(307)] == [CAPTURED_AT] * 4
        assert {lot.server for lot in store.latest_prices(307)} == {"Ilyzaelle"}
    finally:
        store.close()


def run_with_lot_envelope(tmp_path: Path, extra: list[str]) -> int:
    def fake_capture(pipeline: PacketPipeline, interface: str | None) -> None:
        pipeline.on_envelope(lot_envelope(), FLOW_KEY)

    return run_cli(["run", "--db", str(tmp_path / "p.db"), *extra], fake_capture)


def test_cli_run_verbose_prints_the_decoded_table(tmp_path: Path, capsys) -> None:
    assert run_with_lot_envelope(tmp_path, ["--verbose"]) == 0
    output = capsys.readouterr().out
    assert "Lots - objet 307 (10:29:17 UTC)" in output
    assert " 1000   499 999" in output


def test_cli_run_without_verbose_prints_no_table(tmp_path: Path, capsys) -> None:
    assert run_with_lot_envelope(tmp_path, []) == 0
    assert "Lots - objet" not in capsys.readouterr().out


def test_cli_run_reports_unwritable_database(tmp_path: Path, capsys) -> None:
    called: list[bool] = []
    database = tmp_path / "no_such_dir" / "p.db"
    assert run_cli(["run", "--db", str(database)], lambda pipeline, interface: called.append(True)) != 0
    assert str(database) in capsys.readouterr().err
    assert not called


def test_cli_run_reports_capture_failure_after_draining(tmp_path: Path, capsys) -> None:
    database = tmp_path / "p.db"

    def failing_capture(pipeline: PacketPipeline, interface: str | None) -> None:
        pipeline.on_envelope(lot_envelope(), FLOW_KEY)
        raise OSError("npcap missing")

    assert run_cli(["run", "--db", str(database)], failing_capture) != 0
    assert "Capture impossible" in capsys.readouterr().err
    store = PriceStore(str(database))
    try:
        assert len(store.latest_prices(307)) == 4
    finally:
        store.close()


def test_cli_run_reports_aborted_capture(tmp_path: Path, capsys) -> None:
    def aborting_capture(pipeline: PacketPipeline, interface: str | None) -> None:
        raise CaptureAborted("boom")

    assert run_cli(["run", "--db", str(tmp_path / "p.db")], aborting_capture) != 0
    assert "boom" in capsys.readouterr().err


def test_read_commands_report_a_file_that_is_not_a_database(tmp_path: Path, capsys) -> None:
    garbage = tmp_path / "garbage.db"
    garbage.write_text("this is not a sqlite database " * 20, encoding="utf-8")
    before = garbage.read_bytes()
    for command in (["prices"], ["export-csv", "--output", str(tmp_path / "o.csv")]):
        assert run_cli([*command, "--db", str(garbage)]) != 0
        assert "Base de données illisible" in capsys.readouterr().err
    assert garbage.read_bytes() == before


def test_read_commands_report_a_directory_as_database(tmp_path: Path, capsys) -> None:
    assert run_cli(["prices", "--db", str(tmp_path)]) != 0
    assert "est un dossier" in capsys.readouterr().err


def test_empty_selection_says_nothing_matches(tmp_path: Path, capsys) -> None:
    seed(tmp_path / "p.db")
    assert run_cli(["prices", "--item", "5", "--db", str(tmp_path / "p.db")]) == 0
    assert "pour cette sélection" in capsys.readouterr().out


def test_window_command_is_registered_and_dispatched(monkeypatch) -> None:
    seen: list[object] = []
    monkeypatch.setitem(cli.READ_COMMANDS, "window", lambda arguments: seen.append(arguments) or 0)
    assert cli.run(["window", "--server", "Brial"], capture=lambda pipeline, interface: None) == 0
    assert seen[0].server == "Brial" and seen[0].db == cli.DEFAULT_DATABASE


def add_item_name(path: Path) -> None:
    store = PriceStore(str(path))
    try:
        store.connection.execute("INSERT INTO items (item_id, name_fr, type_fr) VALUES (307, 'Ailes de Moskito', 'Ressource')")
        store.connection.commit()
    finally:
        store.close()


def test_cli_prices_shows_item_names_and_na_for_unknown(tmp_path: Path, capsys) -> None:
    seed(tmp_path / "p.db")
    add_item_name(tmp_path / "p.db")
    assert run_cli(["prices", "--db", str(tmp_path / "p.db")]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert any("307" in line and "Ailes de Moskito" in line and "Ressource" in line for line in lines)
    assert any("999" in line and "N/A" in line for line in lines)


def test_cli_prices_shows_na_without_items_table(tmp_path: Path, capsys) -> None:
    seed(tmp_path / "p.db")
    assert run_cli(["prices", "--db", str(tmp_path / "p.db")]) == 0
    assert "N/A" in capsys.readouterr().out


def test_cli_stats_title_has_the_item_name(tmp_path: Path, capsys) -> None:
    seed(tmp_path / "p.db")
    add_item_name(tmp_path / "p.db")
    assert run_cli(["stats", "307", "--db", str(tmp_path / "p.db")]) == 0
    assert "Objet 307 : Ailes de Moskito (Ressource)" in capsys.readouterr().out
