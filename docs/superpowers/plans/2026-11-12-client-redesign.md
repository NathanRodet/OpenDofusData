# Refonte du client (V2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the player window into a full-size, responsive data browser (HDV, Brisage, Familiers, Logs, Réglages) over the local SQLite database, with everything always collected, then reset the collected data and ship it as version 2.0.0.

**Architecture:** Pure logic first (periods, price rules, pet and breaking economics, chart geometry, table sorting), then read-only SQLite view-data modules that turn rows into display rows, then Tk widgets (table, chart, period bar, split layout), then one page per view, then the shell. Capture and decoding are untouched except removing the consent filter.

**Tech Stack:** Python 3.13, CustomTkinter 6 with `tkinter.ttk.Treeview` and `tkinter.Canvas` (no new dependency), SQLite (standard library), pytest. Venv `.venv`, commands through `.\dev.ps1`.

**Spec:** [docs/superpowers/specs/2026-11-12-client-redesign-design.md](../specs/2026-11-12-client-redesign-design.md); mockup [2026-11-12-client-redesign-mockup.html](../specs/2026-11-12-client-redesign-mockup.html) (example values; only Boue du Boo 9 for +1 XP and Patte de Gruche 1 for +2 XP are real).

## Global Constraints

- CLAUDE.md rules: functions at most 20 lines, one responsibility; modules at most 200 lines; English `snake_case` / `PascalCase` / `UPPER_CASE` names; no magic numbers (named constants); type annotations on all signatures; short docstring on public functions; no bare `except:`, no silently swallowed errors, logging via `logging`; pytest tests on synthetic data for every logic module; one module per layer, dependencies one way; pure logic imports neither Scapy, Tk nor SQLite.
- Existing `tests/test_layering.py` must stay green: `capture_session`, `run_pipeline`, `storage`, etc. must not import `window_view`, `app_config`, tkinter, urllib. New view-data modules may import `sqlite3`; new pure modules (`time_filters`, `price_rules`, `pet_economy`, `breaking_economy`, `chart_geometry`, `table_model`, `value_format`, `log_filters`) must not.
- UI is dark only, no "·" separators, no ▸ / ▾ expanders in tables, no CSV export, no on/off switches, no "Voir les prix en ligne".
- Window: minimum 760×480; detail panel right of the table from 1100 px wide, below it otherwise; below 760 px the menu becomes a top bar; menu is 220 px wide with five entries in this order: HDV, Brisage, Familiers, Logs, Réglages.
- Dates are stored in UTC (`...Z`); the UI converts to local time. "Aujourd'hui" starts at local midnight. Table dates show elapsed time ("il y a 12 min" under 60 min, "il y a 3 h" under 24 h, "il y a 2 j" after), exact local date on hover; sorting uses the real date.
- Periods, in this order: Dernière heure, 6 heures, Aujourd'hui, 7 jours, 30 jours, Tout, Personnalisé; default Aujourd'hui; each view keeps its own choice; the filter applies to the capture date (`captured_at`).
- Server is not a filter: views show only the server chosen in Réglages.
- `PET_TOTAL_EXPERIENCE = 179_591`. A resource is one row across all pets. Experience gain = after − before; unusable upgrades (missing experience, gain ≤ 0, or more than one resource) never enter the ratio; `MIN_RELIABLE_EXPERIENCE = 10` XP observed or the row is "peu fiable". Calculations keep all decimals; only display rounds.
- Price setting "Prix utilisé pour les estimations": `last` (default, "Dernier prix HDV"), `median` ("Médian 24 h"), `mean` ("Moyen 24 h"); stored in `config.json` under `price_mode`. Unit price: `last` = lot ×1 price, else smallest lot price divided by its size; price 0 is a valid price (not unknown).
- Brisage: Valeur estimée de l'objet = mean 24 h × quantity; Valeur HDV de l'objet = last price × quantity; Valeur estimée des runes = sum of quantity × unit price per the setting (unknown rune counts 0 and marks the value "partielle"; none known gives "Inconnu"); Plus-value = runes value − Valeur HDV (unknown when the object price is unknown). Default sort: Plus-value descending, unknown last.
- Familiers default sort: kamas per XP ascending, unknown last. Unknown prices display "Inconnu".
- At most `TABLE_ROW_LIMIT = 5_000` rows are drawn; beyond that a notice says so.
- Version 2.0.0.

## Review Focus

1. Empty database or empty period: every page renders with no rows, "Inconnu" or a dash, no exception (Tasks 8, 12, 13, 14, 15).
2. Database read while the capture thread writes (locked or missing file, table absent): the page keeps its previous rows and logs a warning (Task 7).
3. Very large tables (50 000 lot rows): drawing stops at 5 000 rows with a notice and the window stays responsive (Tasks 10, 12).
4. Unknown price, price 0, XP gain 0 or negative, single versus several resources: "Inconnu", sorted last, never a `ZeroDivisionError` (Tasks 3, 4, 5).
5. Server change in Réglages and local midnight / DST boundaries for "Aujourd'hui": views show only the new server; the period start is correct on a DST change day (Tasks 2, 12, 16).

## File Structure

Pure (create): `time_filters.py`, `price_rules.py`, `pet_economy.py`, `breaking_economy.py`, `chart_geometry.py`, `table_model.py`, `value_format.py`, `log_filters.py`.
Data access (create): `price_book.py`, `hdv_view_data.py`, `breaking_view_data.py`, `pets_view_data.py`, `view_connection.py`, `reset_data.py`.
UI (create): `ui_table.py`, `ui_chart.py`, `ui_period.py`, `ui_split.py`, `page_hdv.py`, `page_breaking.py`, `page_pets.py`, `settings_prices.py`, `settings_about.py`.
UI (rewrite): `page_logs.py`, `page_settings.py`, `window_view.py`, `window_pages.py`, `window_context.py`, `ui_theme.py`.
Delete: `page_home.py`, `page_data.py`, `page_about.py`, consent parts of `categories.py`. All under `src/opendofusdata/`; tests under `tests/` with the same name prefixed `test_`.

---

### Task 1: Always collect (remove consent)

**Files:** Modify `categories.py`, `capture_session.py`, `run_pipeline.py`, `cli.py`, `window_command.py`, `window_pages.py`, `window_context.py`, `README.md`; delete `categories_commands.py`, `page_data.py`, `tests/test_categories_commands.py`, `tests/test_run_consent.py`; update `tests/test_categories.py`, `test_capture_session.py`, `test_page_data_logs.py`, `test_cli.py`.

**Interfaces:**
- Produces: `categories.py` keeps only labels and `category_of(record: Record) -> str`; constants `CATEGORY_HDV`, `CATEGORY_BREAKING`, `CATEGORY_PETS`, `CATEGORY_LABELS: dict[str, str]`. No `CategorySettings`, `FilteringWriter`, `categories_from_config`, `config_with_categories`, `ENABLED_KEY`.
- `CaptureSession.__init__(..., feed: LogFeed | None = None)` loses `categories`; `SessionSnapshot` unchanged.

- [ ] **Step 1: Write failing tests.** In `tests/test_run_pipeline.py` (or a new `tests/test_always_collect.py`): `test_every_category_is_stored_without_any_config` runs the `run` command with a capture that emits a lot, a break and a pet upgrade (reuse the helpers of the deleted `test_run_consent.py`: `tests.test_breaking.break_request/broken/outcome`, `tests.window_messages.added`, `tests.envelopes.lot_envelope`) and no `config.json`; asserts `latest_prices()`, `broken_items(...)` each non-empty. `test_enabled_categories_in_an_old_config_are_ignored` writes `{"enabled_categories": []}` and asserts the same.
- [ ] **Step 2: Run** `pytest tests/test_always_collect.py -v`; expect FAIL (hdv-only default).
- [ ] **Step 3: Implement.** Remove `FilteringWriter` wrapping in `capture_session.py` and `run_pipeline.run_command`; reduce `categories.py`; delete the `categories` CLI command and its registration; remove `DataPage` from `window_pages.py` (menu temporarily `("Accueil", "Logs", "Réglages", "À propos")`); drop the categories fields from `WindowContext` users. Delete the obsolete tests; fix the rest.
- [ ] **Step 4: Run** `.\dev.ps1 test`; expect all pass.
- [ ] **Step 5: Commit** `feat: always collect every category, remove the consent switches`.

### Task 2: Periods and elapsed time (pure)

**Files:** Create `time_filters.py`, `tests/test_time_filters.py`.

**Interfaces:**
- Produces: constants `PERIOD_LAST_HOUR="Dernière heure"`, `PERIOD_SIX_HOURS="6 heures"`, `PERIOD_TODAY="Aujourd'hui"`, `PERIOD_WEEK="7 jours"`, `PERIOD_MONTH="30 jours"`, `PERIOD_ALL="Tout"`, `PERIOD_CUSTOM="Personnalisé"`, `PERIODS: tuple[str, ...]` in that order; `@dataclass(frozen=True) PeriodSelection(period: str = PERIOD_TODAY, custom_start: datetime | None = None, custom_end: datetime | None = None)`; `period_window(selection: PeriodSelection, now: datetime, local_zone: tzinfo | None = None) -> tuple[datetime | None, datetime | None]` (aware UTC bounds, `None` = unbounded); `elapsed_text(moment: datetime, now: datetime) -> str`; `local_text(moment: datetime, local_zone: tzinfo | None = None) -> str` (`"12/11 18:42"`); `parse_stored(text: str) -> datetime` (reuses `timeutil`, aware UTC).

- [ ] **Step 1: Failing tests** (names and spec values): `test_last_hour_starts_sixty_minutes_ago`; `test_today_starts_at_local_midnight_converted_to_utc` with zone `UTC+01:00` and now 2026-11-12 23:30 UTC (next local day) giving start 2026-11-12 23:00 UTC; `test_today_on_a_dst_change_day` with `zoneinfo.ZoneInfo("Europe/Paris")` on 2026-10-25 (25 h day) giving start 2026-10-24 22:00 UTC; `test_all_has_no_bounds`; `test_custom_uses_its_bounds`; `test_elapsed_text`: 30 s → "il y a 1 min", 12 min → "il y a 12 min", 59 min → "il y a 59 min", 60 min → "il y a 1 h", 5 h 59 min → "il y a 5 h", 24 h → "il y a 1 j", 49 h → "il y a 2 j", future moment → "il y a 1 min".
- [ ] **Step 2: Run** `pytest tests/test_time_filters.py -v`; expect FAIL (module missing).
- [ ] **Step 3: Implement** the signatures above; compute "Aujourd'hui" by localising `now` and taking midnight of that local date (works across DST).
- [ ] **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: period filters and elapsed time text`.

### Task 3: Price rules and the price setting (pure)

**Files:** Create `price_rules.py`, `tests/test_price_rules.py`; modify `client_settings.py` (+ `tests/test_client_settings.py`).

**Interfaces:**
- Produces: `PRICE_LAST="last"`, `PRICE_MEDIAN="median"`, `PRICE_MEAN="mean"`, `PRICE_MODES`, `PRICE_MODE_LABELS: dict[str, str]` (`"Dernier prix HDV"`, `"Médian 24 h"`, `"Moyen 24 h"`); `@dataclass(frozen=True) ItemPrices(lots: Mapping[int, int], median_24h: int | None, mean_24h: int | None)` (lots: latest price by lot size); `unit_price(prices: ItemPrices | None, mode: str) -> float | None`; in `client_settings.py`: `price_mode_from_config(config: Mapping[str, object]) -> str` (default `PRICE_LAST`, unknown value falls back) and `config_with_price_mode(config, mode) -> dict[str, object]`.

- [ ] **Step 1: Failing tests:** `test_last_price_uses_lot_one`; `test_last_price_without_lot_one_divides_the_smallest_lot` (`{10: 5410, 100: 52300}` → 541.0); `test_median_and_mean_modes`; `test_price_zero_is_a_price` (`{1: 0}` → 0.0); `test_unknown_when_nothing_is_known` (`None` and `ItemPrices({}, None, None)` → None); `test_median_mode_without_stats_is_unknown`; settings: `test_price_mode_defaults_to_last_and_ignores_garbage`.
- [ ] **Step 2: Run**; expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: unit price rules and the price setting`.

### Task 4: Pet economy and number formatting (pure)

**Files:** Create `pet_economy.py`, `value_format.py`, `tests/test_pet_economy.py`, `tests/test_value_format.py`.

**Interfaces:**
- Consumes: `records.PetFeeding`, `PetState`.
- Produces in `pet_economy.py`: `PET_TOTAL_EXPERIENCE = 179_591`, `MIN_RELIABLE_EXPERIENCE = 10`; `@dataclass(frozen=True) ResourceExperience(item_id: int, feedings: int, units: int, experience: int)` (usable single-resource upgrades only; `feedings` counts them); `feeding_gain(feeding: PetFeeding) -> int | None` (None when experience missing or gain ≤ 0); `experience_by_resource(feedings: Iterable[PetFeeding]) -> dict[int, ResourceExperience]` (only upgrades with exactly one resource and a usable gain); `experience_per_unit(stats: ResourceExperience) -> float | None`; `kamas_per_experience(unit_price: float | None, per_unit: float | None) -> float | None` (None if either is None or `per_unit <= 0`); `leveling_cost(kamas_per_xp: float | None) -> float | None`; `is_reliable(stats: ResourceExperience) -> bool`.
- Produces in `value_format.py`: `UNKNOWN_TEXT = "Inconnu"`; `format_kamas(value: float | None) -> str` (integer, thin-space-free regular spaces as thousands separator); `format_signed_kamas(value: float | None) -> str` (`+15 880` / `-1 260`); `format_kamas_per_experience(value: float | None) -> str` (integer from 10, one decimal with a comma below); `format_experience_per_unit(value: float | None) -> str` (integer with `+` from 1, `"1 XP pour N"` with N = round(1/value) below 1).

- [ ] **Step 1: Failing tests** with spec values: Boue du Boo feeding of 9 units gaining 1 XP gives `experience_per_unit == 1/9` and `format_experience_per_unit(1/9) == "1 XP pour 9"`; Patte de Gruche 1 unit gaining 2 XP: per unit 2.0, `format_experience_per_unit(2.0) == "+2"`, price 240 gives kamas per XP 120.0 and `leveling_cost == 120 * 179_591 == 21_550_920`, `format_kamas(21_550_920.0) == "21 550 920"`; `format_kamas_per_experience(7.5) == "7,5"`, `(120.0) == "120"`; two feedings (1 unit +2, 3 units +6) of one resource aggregate to units 4, experience 8, feedings 2; a feeding with two resources, one with `experience=None`, one with gain 0 and one with negative gain are all excluded (`experience_by_resource` empty); `is_reliable` is False at 9 XP and True at 10; `kamas_per_experience(0.0, 2.0) == 0.0`; `kamas_per_experience(240.0, 0.0) is None`; all `format_*` of None return `"Inconnu"`.
- [ ] **Step 2: Run** `pytest tests/test_pet_economy.py tests/test_value_format.py -v`; expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: pet experience economics and price formatting`.

### Task 5: Breaking economy (pure)

**Files:** Create `breaking_economy.py`, `tests/test_breaking_economy.py`.

**Interfaces:**
- Produces: `@dataclass(frozen=True) RunesValue(total: float | None, partial: bool)`; `runes_value(runes: Sequence[tuple[int, int]], price_of: Callable[[int], float | None]) -> RunesValue` (`total=None` when no rune has a price; unknown runes count 0 and set `partial=True`); `object_value(unit_price: float | None, quantity: int) -> float | None`; `plus_value(runes: RunesValue, object_hdv_value: float | None) -> float | None` (None if either is None).

- [ ] **Step 1: Failing tests:** runes `((1557, 3), (1522, 12), (1519, 9))` with prices `{1557: 11200.0, 1522: 100.0, 1519: 120.0}` give total 35 880.0 and `partial` False; same with 1522 unknown gives 34 680.0 and `partial` True; none known gives `total is None`; `plus_value(RunesValue(35880.0, False), 20000.0) == 15880.0`; `plus_value(RunesValue(None, False), 20000.0) is None`; `object_value(900.0, 2) == 1800.0`; `object_value(None, 2) is None`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: breaking value and plus-value rules`.

### Task 6: Chart geometry and table sorting (pure)

**Files:** Create `chart_geometry.py`, `table_model.py`, `tests/test_chart_geometry.py`, `tests/test_table_model.py`.

**Interfaces:**
- `chart_geometry.py`: `value_ticks(low: float, high: float, count: int = 5) -> list[float]` (equally spaced, `count` values, a flat range is widened by 1); `time_ticks(start: datetime, end: datetime, local_zone: tzinfo | None = None) -> list[tuple[datetime, str]]` (every 4 h with `"HH:00"` labels, `"JJ/MM"` at local midnight; every local midnight when the span exceeds 2 days); `scale(value: float, low: float, high: float, pixels: float) -> float` (linear, inverted not applied).
- `table_model.py`: `@dataclass(frozen=True) TableRow(key: object, cells: tuple[str, ...], sort_values: tuple[object, ...], tag: str | None = None)`; `sort_rows(rows: Sequence[TableRow], column: int, descending: bool) -> list[TableRow]` (values equal to `None` always last, whatever the direction; stable); `limit_rows(rows: Sequence[TableRow], limit: int) -> tuple[list[TableRow], bool]` (second item: truncated); constant `TABLE_ROW_LIMIT = 5_000`.

- [ ] **Step 1: Failing tests:** `value_ticks(500, 812)` has 5 items from 500.0 to 812.0; `value_ticks(8.0, 8.0)` widened; `time_ticks` over 24 h gives 4-hour labels like `"00:00"`→ shown as the date `"12/11"` at midnight; over 5 days gives one tick per day; `sort_rows` ascending `(3, None, 1)` → `(1, 3, None)`, descending → `(3, 1, None)`; `limit_rows` of 5 001 rows returns 5 000 and `True`; 5 000 rows returns `False`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: chart geometry and table sorting helpers`.

### Task 7: Price book and the read-only connection

**Files:** Create `view_connection.py`, `price_book.py`, `tests/test_view_connection.py`, `tests/test_price_book.py`.

**Interfaces:**
- Consumes: `item_labels.read_only_uri`, `price_rules.ItemPrices`, tables `lot_prices`, `market_stats` (via `storage.PriceStore` in tests).
- Produces: `READ_TIMEOUT_SECONDS = 1.0`; `open_view_connection(path: str) -> sqlite3.Connection | None` (read-only, `None` and a logged warning when the file is missing or unreadable); `@dataclass PriceBook` with classmethod `PriceBook.load(connection: sqlite3.Connection, server: str) -> PriceBook` (raises `sqlite3.Error` upward) and methods `prices_of(item_id: int) -> ItemPrices | None`, `unit_price(item_id: int, mode: str) -> float | None`, `price_at(item_id: int, moment: datetime) -> float | None` (lot ×1 price captured at or before `moment`, else `None`).

- [ ] **Step 1: Failing tests:** `open_view_connection` of a missing path returns None and logs a warning (`caplog`); a connection cannot write (`INSERT` raises `sqlite3.OperationalError`); `PriceBook.load` on a DB with two lot ×1 prices for item 7 (10:00 price 100, 12:00 price 120) and a 24h stat row gives `unit_price(7, "last") == 120.0`, `unit_price(7, "median")` = stat median, `price_at(7, 11:00 moment) == 100.0`, `price_at(7, 09:00) is None`; other server's rows are ignored; a database without the tables raises `sqlite3.OperationalError` from `load`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement** (two queries per load: latest lot price per `(item_id, lot_size)`, latest `24h` stats row per item, both filtered by server; lot history kept in memory sorted by time for `price_at`, capped per item at 500 entries). **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: read-only connection and price book`.

### Task 8: HDV view data

**Files:** Create `hdv_view_data.py`, `tests/test_hdv_view_data.py`.

**Interfaces:**
- Consumes: `PriceBook`, `time_filters`, `item_labels.ItemLabeler/ItemTyper`.
- Produces: `@dataclass(frozen=True) HdvRow(item_id: int, name: str, type_name: str, last_price: int | None, median_24h: int | None, sold_24h: int | None, last_seen: datetime)`; `hdv_rows(connection, server: str, window: tuple[datetime | None, datetime | None], name_of: ItemLabeler, type_of: ItemTyper) -> list[HdvRow]` (items with a lot or stats row captured inside the window; `last_price` = latest lot ×1); `CurvePoint(moment: datetime, price: int, quantity: int)`; `@dataclass(frozen=True) HdvDetail(item_id: int, name: str, type_name: str, stats: dict[str, tuple[int, int, int]], curves: dict[str, list[CurvePoint]], lots: dict[int, int], history: list[LotPrice])` (`stats[period] = (median, mean, sold_count)` for `"24h"`, `"7d"`, `"30d"`; `history` newest first, at most 500); `hdv_detail(connection, server, item_id, name_of, type_of) -> HdvDetail`.

- [ ] **Step 1: Failing tests** through `PriceStore` (save lots and stats): a window excluding an old record drops that item; two servers are separated; the Flèche du Chafer Archer stats (median 0, mean 0, sold 108) are returned unchanged; `curves["24h"]` returns the saved points as `CurvePoint` in time order; an empty database returns `[]`; `hdv_detail` of an unknown item returns empty stats and curves, no exception.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement** (one SQL per concern; no per-row queries). **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: HDV view data`.

### Task 9: Breaking and pet view data

**Files:** Create `breaking_view_data.py`, `pets_view_data.py`, `tests/test_breaking_view_data.py`, `tests/test_pets_view_data.py`.

**Interfaces:**
- Consumes: `PriceBook`, `breaking_economy`, `pet_economy`, `price_rules`, `breaking_store.broken_items`, `pets_store.pet_feedings`.
- `breaking_view_data.py`: `@dataclass(frozen=True) BreakingRow(moment: datetime, item_id: int, name: str, quantity: int, coefficient: float, runes: tuple[tuple[int, int], ...], estimated_value: float | None, hdv_value: float | None, runes_value: RunesValue, plus_value: float | None)`; `breaking_rows(connection, server, window, name_of, book: PriceBook, mode: str) -> list[BreakingRow]` (default order: plus-value descending, unknown last); `@dataclass(frozen=True) BreakingDetail(item_id: int, name: str, last_coefficient: float, mean_coefficient: float, count: int, points: list[tuple[datetime, float, int]], last_runes: list[tuple[str, int, float | None]], last_row: BreakingRow)`; `breaking_detail(rows: Sequence[BreakingRow], item_id: int, name_of: ItemLabeler, book: PriceBook, mode: str) -> BreakingDetail | None`.
- `pets_view_data.py`: `@dataclass(frozen=True) PetRow(item_id: int, name: str, type_name: str, unit_price: float | None, per_unit: float | None, kamas_per_xp: float | None, feedings: int, last_seen: datetime, cost: float | None, reliable: bool)`; `pet_rows(connection, server, window, name_of, type_of, book, mode) -> list[PetRow]` (default order: `kamas_per_xp` ascending, unknown last); `@dataclass(frozen=True) PetUpgrade(moment: datetime, pet_name: str, units: int, gain: int | None, mixed: bool)`; `@dataclass(frozen=True) PetDetail(row: PetRow, upgrades: list[PetUpgrade], ratio_points: list[tuple[datetime, float, float]])` (ratio points: moment, kamas per XP, unit price at that moment via `book.price_at`); `pet_detail(connection, server, item_id, name_of, type_of, book, mode) -> PetDetail | None`.

- [ ] **Step 1: Failing tests:** breaking: a Cape Maj'Hic row (coefficient 0.44, runes 3/12/9 priced 11200/100/120, object HDV 20 000, mean 19 400, quantity 1) gives runes 35 880.0, plus-value 15 880.0; an unpriced object gives plus-value None sorted last; `breaking_detail` mean of coefficients 0.44, 0.31, 0.41, 0.44 is 0.40 and `count == 4`. Pets: one Boue du Boo upgrade (9 units, 1 XP) plus one Patte de Gruche upgrade (1 unit, +2 XP, price 240) give rows ordered by kamas per XP (Boue unpriced → last); a mixed upgrade (two resources) is absent from rows but present as `PetUpgrade(mixed=True, gain=None)` in the detail of each of its resources; the pet name comes from `name_of(pet_item_id)`; empty DB → `[]` for both.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: breaking and pet view data`.

### Task 10: Table, period bar and split layout widgets

**Files:** Create `ui_table.py`, `ui_period.py`, `ui_split.py`, `tests/test_ui_widgets_v2.py`; modify `ui_theme.py`.

**Interfaces:**
- `ui_theme.py` adds: `SIDEBAR_WIDTH = 220`, `MIN_WIDTH = 760`, `MIN_HEIGHT = 480`, `DEFAULT_WIDTH = 1280`, `DEFAULT_HEIGHT = 800`, `DETAIL_WIDTH = 360`, `SPLIT_BREAKPOINT = 1100`, `COMPACT_BREAKPOINT = 760`, `ROW_HEIGHT = 36`, `UP_COLOR = "#8fd13f"`, `DOWN_COLOR = "#ff7a7a"`; removes `PAGE_MAX_WIDTH`, `LOGS_PAGE_MAX_WIDTH`, `WRAP_LENGTH` usages left by deleted pages.
- `ui_table.py`: `@dataclass(frozen=True) Column(title: str, width: int, numeric: bool = False)`; `class DataTable(frame)` with `__init__(parent, columns: Sequence[Column], on_select: Callable[[object | None], None], default_sort: tuple[int, bool])`, `set_rows(rows: Sequence[TableRow]) -> bool` (re-applies the current sort, keeps the selection by key, uses `limit_rows`, returns truncated), `selected_key() -> object | None`, `sort_by(column: int, descending: bool) -> None`; header click toggles direction; tags `up`/`down` colour rows (`TableRow.tag`); dark ttk style defined once.
- `ui_period.py`: `class PeriodBar(frame)` with `__init__(parent, on_change: Callable[[], None], selection: PeriodSelection = PeriodSelection())`, `selection() -> PeriodSelection`; seven segmented buttons; choosing Personnalisé reveals two date entries (`JJ/MM/AAAA`), invalid input keeps the previous selection and shows a short red message.
- `ui_split.py`: `class SplitLayout(frame)` exposing `main: CTkFrame` and `detail: CTkFrame`; places the detail panel right of `main` (width `DETAIL_WIDTH`) when the width is at least `SPLIT_BREAKPOINT`, below it otherwise, relaying out on `<Configure>`.

- [ ] **Step 1: Failing tests** (use the `tk_root` fixture, skipped without display): `test_table_sorts_on_header_click_and_keeps_unknown_last`; `test_table_keeps_the_selected_row_when_rows_are_replaced`; `test_table_reports_truncation_above_the_limit`; `test_period_bar_defaults_to_today_and_reports_changes`; `test_custom_period_rejects_a_bad_date`; `test_split_layout_moves_the_detail_below_when_narrow` (`root.geometry` 900 px → detail below, 1300 px → right; call `update_idletasks`).
- [ ] **Step 2: Run** `pytest tests/test_ui_widgets_v2.py -v`; expect FAIL. **Step 3: Implement** with `ttk.Treeview` styled dark. **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: table, period bar and split layout widgets`.

### Task 11: Dated chart widget

**Files:** Create `ui_chart.py`, `tests/test_ui_chart.py`.

**Interfaces:**
- Consumes: `chart_geometry`, `time_filters.local_text`.
- Produces: `@dataclass(frozen=True) ChartPoint(moment: datetime, value: float, detail: str)`; `class DatedChart(canvas frame)` with `__init__(parent, height: int = 210)`, `set_series(points: Sequence[ChartPoint], unit: str, decimals: int = 0) -> None` and `clear() -> None`; draws left price axis (5 ticks), bottom date axis (`time_ticks`), filled line, dots, and a tooltip near the point nearest the pointer showing local date, `value unit`, and `detail`; redraws on `<Configure>`; an empty series shows the text "Pas encore de données".

- [ ] **Step 1: Failing tests** (`tk_root`): `test_chart_draws_one_dot_per_point` (count canvas items tagged `dot` after `set_series` of 3 points); `test_chart_without_points_shows_the_empty_text`; `test_tooltip_text_names_date_value_and_detail` calls the nearest-point helper directly and expects `"12/11 18:42"`, `"557 kamas"`, `"46 objets vendus"`; `test_single_point_does_not_crash`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement** (Canvas; geometry from Task 6). **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: dated chart widget`.

### Task 12: HDV page

**Files:** Create `page_hdv.py`, `tests/test_page_hdv.py`.

**Interfaces:**
- Consumes: Tasks 2, 3, 7, 8, 10, 11; `WindowContext.session` (`database_path`, `server`), `WindowContext.name_of`, `type_of` (add `type_of: ItemTyper` to `WindowContext` with default `lambda item_id: "N/A"`).
- Produces: `class HdvPage` with `frame`, `render(snapshot: SessionSnapshot) -> None`; columns Objet, Type, Dernier prix ×1, Médian 24 h, Vendus 24 h, Dernier relevé (elapsed text; the exact local date is shown as a hover tooltip through a Treeview motion binding where feasible, and always in the detail panel; sorting uses the real date kept in `TableRow.sort_values`); default sort: last seen descending; detail: name, level/type pills, Médian/Moyen/Vendus tiles, 24 h / 7 j / 30 j chart tabs (`ChartPoint.detail` = `"N objets vendus"`, unit `"kamas"`), lots ×1/×10/×100, history list; refresh at most every `REFRESH_SECONDS = 2` and immediately on filter or selection change; a failed read keeps the previous rows.

- [ ] **Step 1: Failing tests** (`tk_root`, temp DB through `PriceStore`): `test_page_lists_items_of_the_selected_server_only`; `test_selecting_a_row_fills_the_detail_and_the_chart`; `test_empty_database_shows_no_rows_and_no_error`; `test_search_filters_rows_by_name`; `test_missing_database_file_keeps_the_page_alive` (no exception, Review Focus 2); `test_changing_the_session_server_changes_the_rows` (Review Focus 5).
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: HDV page`.

### Task 13: Brisage page

**Files:** Create `page_breaking.py`, `tests/test_page_breaking.py`. Interfaces consumed: Tasks 5, 9, 10, 11.

- Produces `class BreakingPage` (`frame`, `render(snapshot)`); columns Il y a, Objet, Quantité, Coefficient (`"44 %"`), Valeur estimée de l'objet, Valeur HDV de l'objet, Valeur estimée des runes (suffix " partielle" when partial), Plus-value (tags `up` / `down`); default sort Plus-value descending; detail: tiles Dernier / Moyen / Brisages, coefficient chart (`unit "%"`, detail `"N runes obtenues"`), runes of the last breaking with unit value, total, Valeur estimée de l'objet, Valeur HDV de l'objet, Plus-value; price mode read from `client_settings.price_mode_from_config(load_config(context.config_path))` at each refresh.
- [ ] **Step 1: Failing tests:** `test_default_sort_puts_the_best_plus_value_first_and_unknown_last`; `test_partial_runes_value_is_labelled`; `test_selecting_an_object_shows_its_coefficient_history`; `test_empty_database_renders`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: Brisage page`.

### Task 14: Familiers page

**Files:** Create `page_pets.py`, `tests/test_page_pets.py`. Interfaces consumed: Tasks 4, 9, 10, 11.

- Produces `class PetsPage`; columns Ressource, Type, Prix d'1 ressource, XP pour 1 ressource, Kamas par XP (the mockup's comparative bar is dropped because a Treeview cannot draw one: show the number and colour the three best rows' cell in `UP_COLOR`; builder's call on how), Observations, Dernier relevé, Coût pour monter un familier; header of the sorted column in accent; default sort Kamas par XP ascending; "peu fiable" appended to the row's Observations cell when not reliable; detail: tiles XP pour 1 ressource / Prix d'1 ressource / Kamas par XP, leveling cost line, chart of kamas per XP over time (`unit "kamas par XP"`, detail `"Prix : N kamas l'unité"`), upgrades list (exact local date, `×N, +G XP`, or `×N, sans XP` for mixed).
- [ ] **Step 1: Failing tests:** `test_rows_are_sorted_by_kamas_per_xp_with_unknown_last`; `test_texts_follow_the_display_rules` (Patte de Gruche shows `"+2"`, `"120"`, `"21 550 920"`; Boue du Boo shows `"1 XP pour 9"`); `test_unreliable_row_is_marked`; `test_price_setting_changes_the_ratio` (median vs last); `test_empty_database_renders`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: Familiers page`.

### Task 15: Logs page

**Files:** Create `log_filters.py`, `tests/test_log_filters.py`; rewrite `page_logs.py`; modify `log_feed.py` (always visible: remove `set_visible`/`is_visible`, `LogFeed.add` always records), `tests/test_log_feed.py`, `tests/test_page_data_logs.py` (rename to `tests/test_page_logs.py`).

**Interfaces:** `log_filters.filter_entries(entries: Sequence[LogEntry], text: str, kind: str, window: tuple[datetime | None, datetime | None], name_of: NameLookup) -> list[LogEntry]` (`kind` one of `KIND_ALL="Tout"`, `"HDV"`, `"Brisage"`, `"Familier"`; text matches the shown name, case-insensitive); `LogsPage` columns Heure (exact local time), Type (colour tag by kind), Objet, Détail, Valeur; chips Tout/HDV/Brisage/Familier, `PeriodBar` (default Aujourd'hui), search field, Vider (clears only the feed).

- [ ] **Step 1: Failing tests:** `test_filter_by_kind_text_and_window`; `test_feed_records_without_being_switched_on`; `test_clear_empties_the_feed_but_not_the_database`; `test_notes_for_unknown_pets_still_appear`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: always-on Logs page with filters`.

### Task 16: Réglages page and the end of Accueil / À propos

**Files:** Create `settings_prices.py`, `settings_about.py`; rewrite `page_settings.py`; delete `page_home.py`, `page_about.py`, `tests/test_ui_updates.py` parts moved; modify `window_pages.py`, `window_view.py` (badge on Réglages), `window_context.py` (remove `open_online`), `app_links.py` (remove `SAAS_URL` if unused), `window_command.py`; update `tests/test_page_settings.py`, `tests/test_ui_updates.py`, `tests/test_window_command.py`.

**Interfaces:** `SettingsPage` shows cards that reflow with `grid` (minimum card width 380 px): Serveur de jeu (existing behaviour, restart on change), Base de données (existing), Noms d'objets (existing download, plus count and date), `PricesCard` (`settings_prices.py`: `CTkOptionMenu` with `PRICE_MODE_LABELS`, saves `config_with_price_mode`), Mises à jour (version, announcement + "Mettre à jour et relancer", logic from the old About page), À propos (`AboutCard`: données collectées "Prix HDV, brisage, familiers", envoi "Aucun pour l'instant", licence "Tous droits réservés"). `PAGE_NAMES = ("HDV", "Brisage", "Familiers", "Logs", "Réglages")`.

- [ ] **Step 1: Failing tests:** `test_price_mode_choice_is_saved_to_the_config` (selecting "Médian 24 h" writes `"price_mode": "median"`); `test_update_announcement_and_button_appear_when_a_version_is_available` (ported from the old About tests); `test_menu_badge_marks_the_settings_entry_when_an_update_exists`; `test_no_online_prices_button_remains`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run** `.\dev.ps1 test`; expect all pass.
- [ ] **Step 5: Commit** `feat: Réglages cards, price setting, update card; remove Accueil and À propos`.

### Task 17: Window shell

**Files:** Rewrite `window_view.py`, `window_pages.py`; modify `window_context.py`, `window_command.py`; update `tests/test_window_view.py`.

**Interfaces:** `CaptureWindow` builds the 220 px menu (title, five entries, bottom status block: dot + "Capture active" / "Capture arrêtée" / "Erreur de capture", rows Serveur, Prix, Brisages, Familiers, Dernier relevé, then the Arrêter / Relancer button), builds the five pages from `build_pages(parent, context) -> dict[str, Page]`, opens at `DEFAULT_WIDTH × DEFAULT_HEIGHT` (capped to the screen), `minsize(MIN_WIDTH, MIN_HEIGHT)`; below `COMPACT_BREAKPOINT` the menu moves to a top row; the periodic refresh renders only the visible page.

- [ ] **Step 1: Failing tests** (`tk_root`): `test_menu_has_the_five_entries_in_order`; `test_status_block_shows_server_counters_and_last_record`; `test_narrow_window_moves_the_menu_to_the_top`; `test_only_the_visible_page_renders` (spy on `render`); `test_closing_still_waits_for_the_capture_to_stop`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run** `.\dev.ps1 test`; expect all pass.
- [ ] **Step 5: Commit** `feat: full-size responsive window shell`.

### Task 18: Reset of the collected data

**Files:** Create `reset_data.py`, `reset_commands.py`, `tests/test_reset_data.py`; modify `cli.py`.

**Interfaces:** `COLLECTED_TABLES = ("lot_prices", "market_stats", "broken_items", "pet_feedings")`; `reset_collected_data(database_path: str, now: datetime) -> Path` (copies the database with `sqlite3.Connection.backup` to `<name>-backup-YYYYMMDD-HHMMSS.db` beside it, then deletes every row of `COLLECTED_TABLES` and `VACUUM`s; reference tables `items` and `servers` are kept; raises `FileNotFoundError` when the database does not exist; returns the backup path); CLI `reset-data [--db PATH] --yes` (refuses without `--yes`, prints the backup path and the counts removed).

- [ ] **Step 1: Failing tests:** `test_reset_empties_collected_tables_and_keeps_names_and_servers`; `test_reset_writes_a_backup_with_the_old_rows`; `test_reset_of_a_missing_database_fails_clearly`; `test_cli_refuses_without_yes_and_changes_nothing`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement.** **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit** `feat: reset-data command with backup`.
- [ ] **Step 6: Run it on the owner's database** (explicit request of the owner, "reset des prix et de toutes les données en base"): make sure no capture or window is running, run `.\dev.ps1 run reset-data --yes`, then check with a `SELECT COUNT(*)` that the four tables are empty and the backup file exists. Report the backup path.

### Task 19: Version 2.0.0 and documentation

**Files:** Modify `src/opendofusdata/__init__.py` (`__version__ = "2.0.0"`), `README.md`, `CLAUDE.md`, `docs/roadmap.md`, `docs/protocol-notes.md` (no change expected), `tests/test_package.py` if it pins the version.

- [ ] **Step 1:** README: replace the window description (five entries, periods, price setting, status block, reset command), remove the consent table and Accueil/Données/À propos rows; CLAUDE.md: "chacune doit être désactivable" becomes "tout est collecté en permanence"; roadmap: V2 done, "plus tard" unchanged (sync, server).
- [ ] **Step 2:** `pytest tests/test_package.py -v`; expect PASS with `2.0.0`.
- [ ] **Step 3:** Run `.\dev.ps1 test` (all green) and `.\dev.ps1 build`; expect `dist\OpenDofusData.exe` produced.
- [ ] **Step 4: Commit** `docs: version 2.0.0, window and reset documented`. Do not tag or publish a release without the owner's go.
