# Interface du client joueur Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer la petite fenêtre tkinter par une fenêtre CustomTkinter à menu latéral (Accueil, Données, Logs, Réglages, À propos), avec interrupteurs de catégories fonctionnels, fil de logs optionnel, choix du serveur et de la base.

**Architecture:** La logique pure (catégories, fil de logs, formatage) est testée sans interface. `CaptureSession` reçoit un filtre de catégories et un fil de logs en chaîne d'écrivains (`FilteringWriter` → `FeedWriter` → `CountingWriter` → `StoreWriter`). La vue est découpée en un module par page; le thread de capture ne touche jamais les widgets (la vue lit des instantanés toutes les 500 ms).

**Tech Stack:** Python 3.13, customtkinter 5.2.2 (6.0.0 existe; 5.2.2 retenue, version stable connue), pytest.

**Spec:** [docs/superpowers/specs/2026-11-11-player-client-ui-design.md](../specs/2026-11-11-player-client-ui-design.md)

## Global Constraints

- Fonctions de 20 lignes maximum, modules de 200 lignes maximum, annotations de type, docstring courte sur les fonctions publiques, constantes nommées, noms anglais, textes affichés en français (CLAUDE.md).
- Thème sombre unique (`customtkinter.set_appearance_mode("dark")`), accent bleu `#3b8ed0`; menu latéral 140 px; colonne de page 480 px maximum centrée; fenêtre minimale 640×400; boutons de menu 116×32, de page 200×32.
- Logs: 200 lignes maximum, masqués par défaut, rien n'est accumulé tant qu'ils sont masqués.
- `enabled_categories` dans `config.json` (clé `enabled_categories`, liste de chaînes), défaut `["hdv"]`; clé `database_path` pour la base.
- Le thread de capture ne touche jamais un widget. Aucun import de tkinter/customtkinter hors de `window_*.py`/`page_*.py`, et seulement de façon différée (le CLI doit fonctionner sans tkinter).
- Pas d'`except` nu; erreurs journalisées via `logging`.

## Review Focus

- Catégorie HDV désactivée pendant la capture: plus aucun enregistrement ni compteur ni log (Task 1, 3).
- Fil de logs désactivé: aucune accumulation; réactivé: repart vide, jamais plus de 200 lignes (Task 2).
- Nom d'objet très long ou absent de la table `items`: coupé avec « … » / `N/A`, jamais de retour à la ligne (Task 2, 6).
- `config.json` corrompu ou `enabled_categories` invalide: retour au défaut sans planter (Task 1).
- Changement de serveur/base pendant une capture: l'état affiché reste celui de la capture en cours jusqu'au prochain démarrage (Task 3).
- Base inaccessible: erreur claire affichée sur l'Accueil (déjà gérée par la session; Task 3 le vérifie avec le nouveau chemin).

---

### Task 1: Catégories de données (logique pure)

**Files:**
- Create: `src/opendofusdata/categories.py`
- Test: `tests/test_categories.py`

**Interfaces:**
- Produces:
  - `CATEGORY_HDV = "hdv"`, `CATEGORIES: tuple[DataCategory, ...]` (HDV `available=True`; `recycling`, `breaking`, `pets` `available=False`), `ENABLED_KEY = "enabled_categories"`
  - `@dataclass(frozen=True) DataCategory(key: str, label: str, available: bool)` (labels: « HDV », « Recyclage des ressources », « Brisage », « Expérience des pets »)
  - `class CategorySettings`: `__init__(enabled: Iterable[str])`, `is_enabled(key: str) -> bool`, `set_enabled(key: str, enabled: bool) -> None`, `enabled_keys() -> list[str]` (ordre de `CATEGORIES`), thread-safe
  - `categories_from_config(config: Mapping[str, object]) -> CategorySettings` (défaut `["hdv"]` si clé absente ou invalide; ignore les clés inconnues)
  - `config_with_categories(config: Mapping[str, object], settings: CategorySettings) -> dict[str, object]`
  - `class FilteringWriter`: `__init__(sink: RecordSink, settings: CategorySettings)`; `submit(record)` ne transmet que si `CATEGORY_HDV` est actif (tous les enregistrements actuels sont HDV)

- [ ] **Step 1: Write the failing tests** (`tests/test_categories.py`): `test_default_is_hdv_only`, `test_invalid_config_value_falls_back_to_default` (valeurs `"hdv"`, `42`, `[1, 2]` → `["hdv"]`), `test_unknown_keys_are_ignored` (`["hdv", "xyz"]` → `["hdv"]`), `test_empty_list_means_nothing_enabled` (`[]` → `[]`, volontaire), `test_set_enabled_round_trips_through_config`, `test_filtering_writer_drops_records_when_hdv_disabled` (avec un `LotPrice` factice et un sink liste), `test_filtering_writer_forwards_when_enabled`.
- [ ] **Step 2: Run** `.\dev.ps1 test` filtré: `.venv\Scripts\python -m pytest tests/test_categories.py -v` → FAIL (module absent).
- [ ] **Step 3: Implement** `categories.py` selon les signatures ci-dessus (verrou `threading.Lock` autour de l'ensemble).
- [ ] **Step 4: Run** le même test → PASS.
- [ ] **Step 5: Commit** `feat: data categories with enable/disable filter`.

### Task 2: Fil de logs (logique pure)

**Files:**
- Create: `src/opendofusdata/log_feed.py`
- Test: `tests/test_log_feed.py`

**Interfaces:**
- Consumes: `LotPrice`, `MarketStats` (`records.py`), `RecordSink`, `ItemLabeler` (`item_labels.py`).
- Produces:
  - `MAX_LOG_LINES = 200`, `LOG_COLUMNS = ("Heure", "Type", "Objet", "Détail", "Valeur")`
  - `@dataclass(frozen=True) LogEntry(moment: datetime, category: str, item_id: int, detail: str, value: str)`
  - `class LogFeed`: `__init__(capacity: int = MAX_LOG_LINES)`; `set_visible(visible: bool)`; `is_visible() -> bool`; `add(record: LotPrice | MarketStats, moment: datetime) -> None` (ne fait rien si masqué); `entries() -> list[LogEntry]` (plus récente d'abord); `clear()`; thread-safe. Passer de masqué à visible vide le fil.
  - `format_log_row(entry: LogEntry, name_of: ItemLabeler) -> tuple[str, str, str, str, str]` (heure locale `%H:%M:%S`, `"HDV"`, nom, détail, valeur)
  - `entry_from_record(record, moment) -> LogEntry`: lot → détail `lot ×10`, valeur prix; stats → détail `stats 24 h` / `stats 7 j` / `stats 30 j`, valeur = médiane. Nombres avec espace comme séparateur de milliers (`82 985`).
  - `class FeedWriter`: `__init__(sink: RecordSink, feed: LogFeed, now: Callable[[], datetime])`; `submit(record)` transmet au sink puis `feed.add`.

- [ ] **Step 1: Write the failing tests**: `test_hidden_feed_accumulates_nothing`, `test_shown_feed_keeps_newest_first`, `test_capacity_is_bounded` (capacité 3, 5 ajouts → 3), `test_showing_again_starts_empty`, `test_lot_row_format` (`lot ×10`, `5 868`), `test_stats_row_labels` (`24h`→`stats 24 h`, `7d`→`stats 7 j`, `30d`→`stats 30 j`), `test_unknown_item_is_na`, `test_feed_writer_forwards_then_feeds`.
- [ ] **Step 2: Run** `pytest tests/test_log_feed.py -v` → FAIL.
- [ ] **Step 3: Implement** `log_feed.py` (deque bornée, verrou).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: bounded log feed of captured records`.

### Task 3: Intégration dans CaptureSession

**Files:**
- Modify: `src/opendofusdata/capture_session.py` (constructeur, `_run`, nouvelle méthode), `tests/test_capture_session.py`
- (si le module dépasse 200 lignes, extraire `_run`/`_stop_writer` dans `capture_runner.py`)

**Interfaces:**
- Consumes: `CategorySettings`, `FilteringWriter` (Task 1); `LogFeed`, `FeedWriter` (Task 2).
- Produces:
  - `CaptureSession.__init__(..., categories: CategorySettings | None = None, feed: LogFeed | None = None)` (défauts: `CategorySettings(["hdv"])`, `LogFeed()`); attributs publics en lecture `categories`, `feed`
  - `CaptureSession.apply_settings(database_path: str, server: str) -> None`: pris en compte au prochain `start()`; `snapshot().server` reste celui de la capture en cours/dernière jusqu'à ce `start()`
  - Chaîne d'écriture dans `_run`: `FilteringWriter(FeedWriter(CountingWriter(writer, counters, now), feed, now), categories)`

- [ ] **Step 1: Write the failing tests** (capture factice émettant des enveloppes comme les tests existants): `test_disabled_hdv_records_are_not_counted_or_stored`, `test_enabled_records_reach_the_feed_when_visible`, `test_apply_settings_while_running_keeps_active_server_until_restart`, `test_apply_settings_new_database_used_on_next_start`, `test_unwritable_database_after_apply_gives_error_snapshot`.
- [ ] **Step 2: Run** `pytest tests/test_capture_session.py -v` → FAIL sur les nouveaux tests.
- [ ] **Step 3: Implement** les changements ci-dessus (réglages en attente sous le même verrou, promus dans `start()`).
- [ ] **Step 4: Run** les tests de la session et `pytest -q` complet → PASS.
- [ ] **Step 5: Commit** `feat: capture session filters categories and feeds the log`.

### Task 4: Réglages persistants, câblage de la commande window, noms d'objets

**Files:**
- Create: `src/opendofusdata/client_settings.py`, `tests/test_client_settings.py`
- Modify: `src/opendofusdata/item_labels.py` (ajout), `src/opendofusdata/window_command.py`, `tests/test_window_command.py`, `tests/test_item_labels.py`
- Modify: `pyproject.toml` (`dependencies` + `customtkinter>=5.2.2,<6`), `requirements.txt` (`customtkinter>=5.2.2,<6`)

**Interfaces:**
- Produces:
  - `DATABASE_KEY = "database_path"`, `DEFAULT_DATABASE = "prices.db"`
  - `database_from_config(config: Mapping[str, object]) -> str | None`
  - `config_with_database(config, path: str) -> dict[str, object]`, `config_with_server(config, name: str) -> dict[str, object]` (utilise `SERVER_KEY`)
  - `server_names() -> list[str]`: noms de `available_servers(DEFAULT_SERVERS_PATH)` triés (casefold)
  - `item_labeler_for_database(path: str) -> ItemLabeler` dans `item_labels.py`: ouvre la base en lecture seule si elle existe, sinon (ou en cas d'erreur `sqlite3.Error`) retourne un labeler qui renvoie `N/A`
  - `@dataclass WindowContext(session: CaptureSession, open_online: Callable[[], None], config_path: Path, server_names: list[str], name_of: ItemLabeler)` dans `window_command.py`
  - La sous-commande `window`: `--db` défaut `None`; priorité `--db` > `database_path` du config > `prices.db`. `show_window(context: WindowContext) -> int`; `CaptureWindow(root, context)`.

- [ ] **Step 1: Write the failing tests**: priorité de `--db`, config absente/corrompue → `prices.db`, `item_labeler_for_database` (base absente → `N/A`; base avec table `items` → le nom), `config_with_*` conservent les autres clés.
- [ ] **Step 2: Run** les nouveaux tests → FAIL.
- [ ] **Step 3: Implement**; adapter les tests de `test_window_command.py` à la nouvelle signature (`show_window(context)`, `FakeWindow(root, context)`, `customtkinter.CTk` à la place de `tkinter.Tk`). Installer la dépendance: `.venv\Scripts\python -m pip install "customtkinter>=5.2.2,<6"`.
- [ ] **Step 4: Run** `pytest -q` (les tests de vue seront adaptés Task 5) → PASS hors vue.
- [ ] **Step 5: Commit** `feat: persistent client settings and window wiring`.

### Task 5: Coque de la fenêtre CustomTkinter et page Accueil

**Files:**
- Create: `src/opendofusdata/ui_theme.py` (constantes: tailles, couleurs, polices), `src/opendofusdata/page_home.py`
- Rewrite: `src/opendofusdata/window_view.py`
- Modify: `src/opendofusdata/window_format.py` (une fonction `home_counts_text` si besoin; sinon inchangé), `tests/test_window_view.py`

**Interfaces:**
- Consumes: `WindowContext` (Task 4), `status_text`, `server_text`, `counts_text`, `last_record_text`, `button_label`, `button_enabled`.
- Produces:
  - `CaptureWindow(root: customtkinter.CTk, context: WindowContext)` avec `start()`, `render()`, `close()`, `show_page(name: str)`, attributs `toggle_button`, `pages: dict[str, Page]`
  - `class Page(Protocol)`: `frame: customtkinter.CTkFrame`; `render(snapshot: SessionSnapshot) -> None`
  - `PAGE_NAMES = ("Accueil", "Données", "Logs", "Réglages", "À propos")`
  - Fonction `make_page_body(parent) -> CTkFrame` (colonne centrée, largeur `PAGE_MAX_WIDTH = 480`, `pack_propagate(False)`)

- [ ] **Step 1: Write the failing tests** (même style que l'actuel, ignorés sans écran): `test_minimum_size_is_640_by_400`, `test_menu_switches_pages`, `test_home_shows_status_and_counts`, `test_stop_button_then_restart`, `test_online_button_calls_the_opener`, `test_close_stops_the_session`.
- [ ] **Step 2: Run** `pytest tests/test_window_view.py -v` → FAIL.
- [ ] **Step 3: Implement** coque (menu 140 px, bouton Arrêter/Relancer 116×32 en bas, `set_appearance_mode("dark")`, `minsize(640, 400)`, titre `APP_NAME`, boucle `after(500)` comme aujourd'hui) et `page_home.py` (état en gros, serveur, compteurs, dernier relevé, bouton « Voir les prix en ligne » 200×32; message d'erreur en encadré rouge quand `ERROR`). Les pages Données/Logs/Réglages/À propos sont des cadres vides provisoires.
- [ ] **Step 4: Run** → PASS; lancer à la main `.venv\Scripts\python -m opendofusdata window` pour un contrôle visuel.
- [ ] **Step 5: Commit** `feat: customtkinter window shell with home page`.

### Task 6: Pages Données et Logs

**Files:**
- Create: `src/opendofusdata/page_data.py`, `src/opendofusdata/page_logs.py`, `tests/test_page_data_logs.py`

**Interfaces:**
- Consumes: `CategorySettings`, `CATEGORIES`, `config_with_categories`, `LogFeed`, `format_log_row`, `LOG_COLUMNS`, `save_config`.
- Produces: `DataPage(parent, context)` et `LogsPage(parent, context)`, tous deux conformes à `Page`.
  - `DataPage`: une ligne par catégorie (libellé, compteur pour HDV = prix + statistiques, `CTkSwitch`); interrupteur inactif et libellé « bientôt » pour les catégories non disponibles; un clic applique `set_enabled` puis sauvegarde le config (échec `OSError` → message d'avertissement dans la page, jamais d'exception).
  - `LogsPage`: `CTkSwitch` « Afficher les logs » (défaut off, appelle `feed.set_visible`), puis un tableau en grille à largeurs fixes (`64, 44, flex, 74, 64`, colonne Valeur alignée à droite, texte coupé avec « … » par une fonction pure `shorten(text: str, limit: int) -> str`), message « Logs masqués… » quand off. Le tableau se rafraîchit dans `render` seulement si le contenu a changé.

- [ ] **Step 1: Write the failing tests**: `test_shorten_adds_ellipsis_and_never_wraps` (pure), `test_unavailable_categories_are_disabled_and_labelled_soon`, `test_toggling_hdv_updates_settings_and_config_file` (config dans `tmp_path`), `test_toggle_survives_unwritable_config` , `test_logs_switch_controls_feed_visibility`, `test_log_table_shows_at_most_200_rows`.
- [ ] **Step 2: Run** `pytest tests/test_page_data_logs.py -v` → FAIL.
- [ ] **Step 3: Implement** les deux pages, brancher dans `window_view.py` à la place des cadres provisoires.
- [ ] **Step 4: Run** → PASS; contrôle visuel avec `opendofusdata window`.
- [ ] **Step 5: Commit** `feat: data categories and logs pages`.

### Task 7: Pages Réglages et À propos

**Files:**
- Create: `src/opendofusdata/page_settings.py`, `src/opendofusdata/page_about.py`, `tests/test_page_settings.py`

**Interfaces:**
- Consumes: `WindowContext.server_names`, `config_with_server`, `config_with_database`, `CaptureSession.apply_settings`, `tkinter.filedialog.asksaveasfilename` (injectable: paramètre `choose_database: Callable[[str], str | None]`).
- Produces: `SettingsPage(parent, context, choose_database=...)`, `AboutPage(parent, context)`.
  - `SettingsPage`: `CTkOptionMenu` du serveur (valeur courante sélectionnée; si absente de la liste elle est ajoutée), chemin de la base en lecture, bouton « Changer l'emplacement » 200×32; chaque changement sauvegarde le config puis appelle `session.apply_settings`; message « Enregistré. Arrête puis relance la capture pour l'appliquer. » si la capture tourne, sinon « Enregistré. » ; erreur d'écriture → message, état inchangé.
  - `AboutPage`: nom, version (`importlib.metadata.version("open-dofus-data")`, repli `"dev"`), ce qui est collecté, « Rien n'est envoyé hors de ta machine dans cette version. », bouton « Voir le dépôt » (adresse `REPOSITORY_URL` ajoutée à `app_links.py`, espace réservé comme `SAAS_URL`).

- [ ] **Step 1: Write the failing tests**: `test_server_choice_is_saved_and_applied`, `test_database_choice_is_saved_and_applied`, `test_cancelled_file_dialog_changes_nothing`, `test_message_asks_restart_while_running`, `test_about_shows_version_fallback`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** les deux pages et les brancher.
- [ ] **Step 4: Run** → PASS; contrôle visuel.
- [ ] **Step 5: Commit** `feat: settings and about pages`.

### Task 8: Documentation et vérification finale

**Files:**
- Modify: `README.md` (section « Fenêtre OpenDofusData »: menu, pages, Logs, interrupteurs, `database_path`/`enabled_categories` dans `config.json`, dépendance `customtkinter`), `docs/roadmap.md` (catégories désactivables: fait; fenêtre: nouvelle interface), `CLAUDE.md` (aucune règle à changer; vérifier la mention de la fenêtre)

- [ ] **Step 1:** Mettre à jour les trois documents.
- [ ] **Step 2:** Vérifier les limites (20 lignes/fonction, 200 lignes/module) sur les fichiers créés ou modifiés avec un petit script ad hoc dans le scratchpad.
- [ ] **Step 3:** `.\dev.ps1 test` complet → tous verts; `opendofusdata window` lancé et inspecté à la main (redimensionnement, interrupteurs, logs).
- [ ] **Step 4: Commit** `docs: document the new player window`.
