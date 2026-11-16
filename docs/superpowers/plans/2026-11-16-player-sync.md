# Synchronisation des prix entre joueurs: plan d'implémentation

> **Pour les agents:** SOUS-COMPÉTENCE OBLIGATOIRE: utiliser superpowers:subagent-driven-development (recommandé) ou superpowers:executing-plans pour exécuter ce plan tâche par tâche. Les étapes utilisent des cases à cocher (`- [ ]`).

**Objectif:** les joueurs envoient leurs prix de lots de l'HDV au serveur de clés (`POST /readings`) et récupèrent ceux des autres (`GET /readings`), avec un journal de 7 jours côté serveur, l'identifiant de la clé émettrice gardé avec chaque relevé, et une révocation au choix avec ou sans suppression des relevés de la clé.

**Architecture:** le serveur (`src/server/keyserver/`) gagne un magasin de relevés SQLite (`readings_store.py`), des routes REST authentifiées par clé utilisateur, une tâche de purge quotidienne, et une option `purge` à la révocation. Le garde-fou de format accepte désormais, pour les routes `GET` déclarées, une liste blanche stricte de paramètres entiers. Le client gagne trois colonnes sur `lot_prices` (`origin`, `synced_at`, `source_key_id`), un état de synchro, un moteur d'envoi et de récupération, un fil d'arrière-plan commandé par deux réglages décochés par défaut, un choix de révocation dans l'onglet Administration, et une purge locale optionnelle des relevés de plus de 7 jours.

**Pile technique:** Python 3.13, FastAPI/Pydantic (serveur), SQLite, `urllib` via `https_json` (client), CustomTkinter (réglages), pytest.

**Spécification:** [docs/superpowers/specs/2026-11-16-player-sync-design.md](../specs/2026-11-16-player-sync-design.md)

## Contraintes globales

- `CLAUDE.md`: fonctions de 20 lignes au plus, modules de 200 lignes au plus (`storage.py` en a 192: tout nouveau code client va dans de nouveaux modules), annotations de type, pas de nombres magiques, pas de `except:` nu, tests sur données synthétiques, dépendances verrouillées (aucune nouvelle dépendance ici).
- Texte: aucun tiret typographique long ni point médian (`tests/test_text_style.py` scanne `src/` et `docs/`).
- Aucune adresse IP de joueur lue, enregistrée ni transmise.
- Identité de l'émetteur (décision du propriétaire): chaque relevé renvoyé porte `key_id`, l'identifiant de 11 caractères de la clé qui l'a envoyé, et le client le garde avec la ligne locale (`source_key_id`). Ce code est un pseudonyme: jamais la clé complète, jamais sa signature, jamais le pseudo choisi par l'administrateur.
- Toute route est déclarée dans `ALLOWED_ROUTES`. Corps limité à 1 Mio, 2000 relevés par lot au plus, schémas stricts.
- Rien ne part sans réglage explicite: `sync_send` et `sync_receive` valent `False` par défaut.
- Commandes de test: serveur `cd src/server && .venv/Scripts/python.exe -m pytest -q`; client (racine) `.venv/Scripts/python.exe -m pytest -q`.
- Messages de commit terminés par `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Décisions prises en écrivant le plan (écarts avec la spécification)

1. **Routes REST classiques (demande du propriétaire):** `POST /readings` (envoi), `GET /readings?since=N&limit=L` (relevés des autres clés arrivés après le numéro N), `GET /readings/latest?after=K&limit=L` (instantané au premier lancement: dernier relevé de chaque serveur, objet et lot). Le garde-fou `check_format` refusait toute chaîne de requête: il accepte maintenant, pour une route et une méthode déclarées, uniquement les paramètres de la liste blanche, chacun une seule fois, valeur entière décimale de 1 à 12 chiffres, sans encodage en pourcentage; tout le reste donne toujours `400 unexpected_query`. Un `GET` avec un corps est refusé (`400 unexpected_body`).
2. **Révocation au choix (demande du propriétaire):** `POST /admin/revoke` accepte `{"key_id": "...", "purge": true|false}`; `purge` vaut `false` si absent (comportement actuel). Dans tous les cas la clé est révoquée d'abord (elle cesse de marcher tout de suite), puis, si `purge` est vrai, ses relevés sont supprimés; deux étapes ordonnées et non une seule transaction (deux connexions sur le même fichier); un second appel est idempotent et reprend la purge si la première a échoué. Sans purge, les relevés de la clé révoquée restent servis jusqu'à la fin de la rétention.
3. **Réponses plus grosses que 64 Kio:** `request_json` reçoit `max_response_bytes` (défaut inchangé); la synchro utilise 1 Mio.
4. **Date d'observation côté serveur:** stockée en entier (secondes Unix UTC), rendue en `YYYY-MM-DDTHH:MM:SSZ` (le format de `captured_at` du client).
5. **Limite connue, voulue par le propriétaire:** une purge côté serveur ne retire pas les relevés déjà récupérés par les clients. `source_key_id` rendrait possible plus tard une propagation de la purge; hors périmètre.
6. **Purge locale optionnelle (demande du propriétaire):** un réglage (décoché par défaut) et un bouton dans Réglages suppriment de la base locale les relevés de prix (`lot_prices`) et de statistiques (`market_stats`) de plus de 7 jours, en gardant toujours la ligne la plus récente de chaque (objet, serveur, lot) ou (objet, serveur, période) pour que l'HDV n'oublie aucun dernier prix connu. Jamais touchés: favoris des familiers, observations manuelles de familiers, noms d'objets, serveurs, brisages, améliorations de familiers, état de synchro.

## Revue ciblée

Entrées et conditions que la spécification suppose sans que les tests des tâches les couvrent d'office; chacune a son test dans la tâche indiquée.

1. Une page de 2000 relevés (environ 250 Ko avec `key_id` et `seq`) traverse l'application sans être tronquée (tâche 4: test de taille de réponse).
2. Chaînes de requête hostiles sur les `GET`: paramètre inconnu, paramètre répété, valeur non entière, valeur à plus de 12 chiffres, `%`-encodage, chaîne de requête sur `/check` (tâche 4: toutes refusées en `400`).
3. Un joueur dont la clé est révoquée pendant un envoi reçoit `401`: le client s'arrête et ne boucle pas (tâche 9: moteur; tâche 10: fil).
4. Un relevé reçu deux fois (coupure après la réponse) ne crée ni doublon serveur ni ligne locale en double (tâches 2 et 4: doublon serveur; tâches 6 et 7: insertion distante unique).
5. Une base locale existante (sans `origin`, `synced_at` ni `source_key_id`) est migrée sans perte, et rien ne part sans `sync_send` (tâche 6: migration; tâches 9 et 10: réglages).

---

### Tâche 1: schémas du relevé de prix de lot et de la révocation

**Fichiers:**
- Modifier: `src/server/keyserver/schemas.py`
- Tester: `src/server/tests/test_schemas.py`, `src/server/tests/test_admin_routes.py` (corps du schéma seulement)

**Interfaces:**
- Produit: `Reading` avec `server: ServerName`, `item_id: int` (1 à `MAX_ITEM_ID`), `lot_size: int` (dans `LOT_SIZES = (1, 10, 100, 1000)`), `price: int` (1 à `MAX_PRICE = 1_000_000_000_000`), `observed_at: ObservationTime`; `ReadingBatch` inchangé; `KeyIdRequest` gagne `purge: bool = False` (booléen strict: `"true"`, `1` refusés); constantes `LOT_SIZES`, `MAX_PRICE`, `MAX_QUERY_INTEGER = 999_999_999_999` (12 chiffres).

- [ ] **Étape 1: tests qui échouent.** Dans `test_schemas.py`: `reading_json` avec `lot_size` et `price`; `test_lot_size_bounds` (valides 1, 10, 100, 1000; refusés 0, 2, 5, 1001, -1, `"10"`, `True`); `test_price_bounds` (valides 1 et `MAX_PRICE`; refusés 0, -5, `MAX_PRICE + 1`, `1.5`, `"750"`, `True`); `test_key_id_request_purge_defaults_to_false_and_is_strict` (absent: faux; `true`: vrai; `"true"`, `1`, `null`: refusés).
- [ ] **Étape 2: constater l'échec.** `cd src/server && .venv/Scripts/python.exe -m pytest tests/test_schemas.py -q`; attendu: échecs sur `lot_size`, `price`, `purge`.
- [ ] **Étape 3: implémenter** les champs et constantes (`STRICT_MODEL`, `Field(ge=..., le=...)`); adapter l'ancien `test_unknown_field_is_rejected`.
- [ ] **Étape 4: tests verts**, puis la suite serveur complète.
- [ ] **Étape 5: commit** `feat(server): price fields in the reading schema and purge option in the revoke body`.

### Tâche 2: magasin de relevés du serveur

**Fichiers:**
- Créer: `src/server/keyserver/readings_store.py`
- Tester: `src/server/tests/test_readings_store.py`

**Interfaces:**
- Consomme: `Reading` (tâche 1).
- Produit: `class StoredReading(NamedTuple): seq: int; key_id: str; server: str; item_id: int; lot_size: int; price: int; observed_at: str` (date `YYYY-MM-DDTHH:MM:SSZ`); `class ReadingStore` avec `add_batch(key_id: str, readings: Sequence[Reading]) -> tuple[int, int]` (acceptés, doublons), `changes_since(key_id: str, since: int, limit: int) -> list[StoredReading]` (relevés d'AUTRES clés, `seq > since`, par `seq`), `latest_page(key_id: str, after: int, limit: int) -> list[StoredReading]` (dernier relevé de chaque (serveur, objet, lot) parmi les autres clés, `seq > after`, par `seq`), `highest_seq() -> int`, `purge_older_than(cutoff: datetime) -> int`, `purge_key(key_id: str) -> int`, `close()`; `open_readings(path) -> ReadingStore`; `RETENTION_DAYS = 7`.

- [ ] **Étape 1: tests qui échouent** (base `":memory:"`): `test_add_batch_counts_accepted_and_duplicates` (même (clé, serveur, objet, lot, date) deux fois: 1 accepté puis 1 doublon, une seule ligne); `test_same_reading_from_two_keys_is_stored_twice`; `test_changes_since_excludes_own_readings_and_orders_by_seq`; `test_changes_since_respects_limit_and_since`; `test_changes_carry_the_sender_key_id`; `test_latest_page_returns_latest_per_natural_key_of_other_keys`; `test_latest_page_pages_with_after`; `test_purge_older_than_removes_only_old_readings`; `test_purge_key_removes_only_that_key`; `test_highest_seq_is_zero_when_empty`; `test_dates_roundtrip_as_utc_iso_seconds`.
- [ ] **Étape 2: constater l'échec** (`ModuleNotFoundError`).
- [ ] **Étape 3: implémenter** la table `readings(seq INTEGER PRIMARY KEY AUTOINCREMENT, key_id TEXT NOT NULL, server TEXT NOT NULL, item_id INTEGER NOT NULL, lot_size INTEGER NOT NULL, price INTEGER NOT NULL, observed_at INTEGER NOT NULL)`, un index unique `(key_id, server, item_id, lot_size, observed_at)`, un index sur `key_id`, un index sur `observed_at`. `add_batch` en une transaction (`INSERT OR IGNORE`, `rowcount`). Même modèle de verrou et de connexion partagée que `RevocationStore`. `latest_page` avec `ROW_NUMBER() OVER (PARTITION BY server, item_id, lot_size ORDER BY observed_at DESC, seq DESC)`. Constantes nommées.
- [ ] **Étape 4: tests verts**, puis la suite serveur.
- [ ] **Étape 5: commit** `feat(server): reading store with batch insert, change feed, latest page and purges`.

### Tâche 3: l'identifiant de la clé disponible pour les routes

**Fichiers:**
- Modifier: `src/server/keyserver/auth.py`
- Tester: `src/server/tests/test_auth.py`

**Interfaces:**
- Consomme: `KeyVerifier`, `parse_key` (existants).
- Produit: après authentification d'une clé utilisateur, `scope["state"]["key_id"]` contient l'identifiant (11 caractères); une route le lit par `request.state.key_id`. Le jeton d'administration ne pose pas `key_id`. Aucune adresse n'est lue.

- [ ] **Étape 1: tests qui échouent**: `test_authorised_user_request_carries_its_key_id` (application ASGI minimale derrière le middleware qui renvoie `scope["state"]["key_id"]`; valeur de test partagée: `AAAAAAAAAAA`); `test_admin_token_request_has_no_key_id`; `test_key_id_is_not_set_for_rejected_requests` (401, l'application interne n'est pas appelée).
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter** `KeyVerifier.verified_key_id(key) -> str | None` (identifiant si la clé est valide et non révoquée) et poser `scope.setdefault("state", {})["key_id"]` avant d'appeler l'application; garder `is_valid`.
- [ ] **Étape 4: tests verts** et suite serveur.
- [ ] **Étape 5: commit** `feat(server): expose the verified key id to the routes`.

### Tâche 4: garde-fou des chaînes de requête, routes de synchro, révocation avec option de purge

**Fichiers:**
- Créer: `src/server/keyserver/reading_routes.py`
- Modifier: `src/server/keyserver/request_rules.py`, `src/server/keyserver/guards.py` (si le garde-fou lit la chaîne de requête), `src/server/keyserver/app.py`, `src/server/keyserver/admin_routes.py`, `src/server/tests/conftest.py`
- Tester: `src/server/tests/test_reading_routes.py`, `src/server/tests/test_request_rules.py`, `src/server/tests/test_admin_routes.py`

**Interfaces:**
- Consomme: `ReadingStore` (tâche 2), `request.state.key_id` (tâche 3), schémas (tâche 1).
- Produit:
  - `ALLOWED_ROUTES: dict[str, frozenset[str]]` contient `"/readings": {"GET", "POST"}`, `"/readings/latest": {"GET"}` en plus de `/check` et `/admin/revoke`; `QUERY_PARAMETERS: dict[tuple[str, str], frozenset[str]]` = `{("/readings", "GET"): {"since", "limit"}, ("/readings/latest", "GET"): {"after", "limit"}}`; `check_format(method, path, query, content_type, has_body)` accepte la chaîne de requête seulement pour ces couples, sinon `400 unexpected_query`; un `GET` avec corps donne `Rejection(400, "unexpected_body")`.
  - `register_reading_routes(app: FastAPI, readings: ReadingStore) -> None`; `create_app(settings, revocations, readings)`; `register_admin_routes(app, revocations, readings)`.
  - `POST /readings` (corps `ReadingBatch`) -> `{"accepted": n, "duplicates": m}`. `GET /readings?since=N&limit=L` (`since` >= 0, `limit` de 1 à 2000, tous deux obligatoires) -> `{"readings": [...], "next": N2}` (`next` = dernier `seq` renvoyé, ou `since` si rien). `GET /readings/latest?after=K&limit=L` -> `{"readings": [...], "next": K2, "as_of": N, "done": bool}` (`done` vrai quand la page compte moins de `limit` relevés). Chaque relevé renvoyé: `seq`, `key_id`, `server`, `item_id`, `lot_size`, `price`, `observed_at`.
  - `POST /admin/revoke` avec `{"key_id", "purge"}`: révoque, puis supprime les relevés de la clé si `purge` est vrai; réponse `{"revoked": true, "purged": n}` (`n` = 0 sans purge).

- [ ] **Étape 1: tests qui échouent** (client de test avec clé valide `make_key(SECRET, KEY_ID)` et une seconde clé d'un autre identifiant):
  - Routes: `test_post_readings_stores_and_reports_counts`; `test_post_same_batch_twice_reports_duplicates`; `test_readings_routes_require_a_user_key` (401 sans clé, avec le jeton d'administration, avec une clé révoquée, pour les trois routes); `test_post_readings_rejects_invalid_body` (422 `invalid_body`: champ en trop, lot 7, prix 0, lot vide, 2001 relevés); `test_get_readings_returns_other_keys_readings_with_seq_key_id_and_next`; `test_get_readings_does_not_return_own_readings`; `test_get_readings_rejects_missing_or_out_of_range_parameters` (422 ou 400 sans détail répété); `test_latest_pages_until_done_and_reports_as_of`; `test_returned_key_id_is_the_eleven_character_id_never_the_full_key` (le corps brut ne contient ni `odk1.` ni la signature); `test_full_page_of_2000_readings_is_served_whole` (2000 relevés stockés, `limit=2000`, corps entier et JSON valide).
  - Garde-fou (`test_request_rules.py`): `test_declared_get_routes_accept_their_own_parameters`; `test_unknown_repeated_non_integer_long_or_percent_encoded_parameters_are_refused` (`since=1&since=2`, `foo=1`, `since=abc`, `since=1.5`, `since=-1`, `since=` plus 13 chiffres, `since=%31`, `since=1&limit=2&x=3`); `test_query_on_check_and_on_post_routes_is_still_refused`; `test_get_with_a_body_is_refused`; `test_allowed_routes_and_query_parameters_are_the_planned_ones`.
  - Révocation (`test_admin_routes.py`): `test_revoke_without_purge_keeps_the_readings_and_answers_purged_zero`; `test_revoke_with_purge_deletes_only_that_key_readings`; `test_revoke_with_purge_twice_is_still_200`; `test_revoke_body_rejects_a_non_boolean_purge`.
  - Mettre à jour `conftest.py` (fixture `readings` en `":memory:"`, `client` avec les trois arguments).
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter** dans cet ordre: `request_rules.py` (analyse stricte de la chaîne de requête par `re.fullmatch` sur `name=digits` séparés par `&`, sans décodage); `reading_routes.py` (paramètres déclarés avec `Query(ge=..., le=...)`, `limit` plafonné à `MAX_BATCH_READINGS`); `create_app` et `build_app` (le magasin s'ouvre dans le même fichier que les révocations: `open_readings(settings.db_path)`); `revoke` (révoque, puis purge si demandé, journalise le nombre sans clé complète).
- [ ] **Étape 4: tests verts**, y compris la suite serveur complète.
- [ ] **Étape 5: commit** `feat(server): REST reading routes, strict query parameters and revocation with optional purge`.

### Tâche 5: rétention de 7 jours

**Fichiers:**
- Créer: `src/server/keyserver/retention.py`
- Modifier: `src/server/keyserver/app.py` (`build_app`)
- Tester: `src/server/tests/test_retention.py`

**Interfaces:**
- Consomme: `ReadingStore.purge_older_than`, `RETENTION_DAYS` (tâche 2).
- Produit: `purge_expired(readings: ReadingStore, now: datetime) -> int`; `start_purge_loop(readings: ReadingStore, interval_seconds: float = PURGE_INTERVAL_SECONDS) -> threading.Event` (fil daemon qui purge au démarrage puis à chaque intervalle; l'événement renvoyé l'arrête); `PURGE_INTERVAL_SECONDS = 86_400`.

- [ ] **Étape 1: tests qui échouent**: `test_purge_expired_uses_the_seven_day_cutoff` (relevés à 6 j 23 h gardés, à 7 j 1 h supprimés, horloge injectée); `test_purge_loop_purges_at_start_and_stops_on_event` (intervalle court, relevé périmé supprimé sans attendre, l'événement termine le fil); `test_build_app_works_with_a_temporary_database`.
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter** `retention.py` (`threading.Event.wait(interval)`, exceptions journalisées sans tuer le fil); `start_purge_loop` appelé dans `build_app` seulement (pas dans `create_app`).
- [ ] **Étape 4: tests verts** et suite serveur.
- [ ] **Étape 5: commit** `feat(server): seven day retention with a daily purge`.

### Tâche 6: colonnes et état de synchro du client

**Fichiers:**
- Créer: `src/opendofusdata/sync_schema.py`
- Modifier: `src/opendofusdata/storage.py` (deux lignes: import et appel dans `PriceStore.__init__`)
- Tester: `tests/test_sync_schema.py`

**Interfaces:**
- Produit: `prepare_sync_schema(connection: sqlite3.Connection) -> None` (idempotent): ajoute à `lot_prices` les colonnes `origin TEXT NOT NULL DEFAULT 'local'`, `synced_at TEXT` et `source_key_id TEXT`, un index partiel des lignes à envoyer `(id) WHERE origin = 'local' AND synced_at IS NULL`, un index unique partiel `(item_id, server, lot_size, captured_at, source_key_id) WHERE origin = 'remote'`, et la table `sync_state(name TEXT PRIMARY KEY, value TEXT NOT NULL)`; constantes `ORIGIN_LOCAL = "local"`, `ORIGIN_REMOTE = "remote"`.

- [ ] **Étape 1: tests qui échouent**: `test_columns_and_state_table_are_created`; `test_migration_keeps_existing_rows_as_local_and_unsent` (base à l'ancien schéma avec une ligne); `test_preparing_twice_changes_nothing`; `test_remote_duplicates_are_refused_by_the_unique_index`; `test_same_reading_from_two_other_keys_is_kept_twice`; `test_price_store_creates_the_sync_columns`; `test_existing_price_queries_return_the_same_columns` (`latest_prices`, `price_history`).
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter** avec `PRAGMA table_info(lot_prices)` pour ne pas ré-ajouter une colonne; appel dans `PriceStore.__init__` après `prepare_extra_tables`; `storage.py` reste sous 200 lignes.
- [ ] **Étape 4: tests verts** (suite client complète).
- [ ] **Étape 5: commit** `feat: sync columns, state table and migration for lot prices`.

### Tâche 7: lecture et écriture des relevés de synchro (client)

**Fichiers:**
- Créer: `src/opendofusdata/sync_store.py`
- Tester: `tests/test_sync_store.py`

**Interfaces:**
- Consomme: `prepare_sync_schema`, `ORIGIN_*` (tâche 6).
- Produit: `class PendingReading(NamedTuple): row_id: int; item_id: int; server: str; lot_size: int; price: int; captured_at: str`; `pending_readings(connection, limit: int) -> list[PendingReading]` (lignes `local` non envoyées, les plus anciennes d'abord, sauf celles que le filtre écarte: une ligne est écartée quand une ligne `local` déjà envoyée existe pour la même clé naturelle (objet, serveur, lot) avec le même prix et une `captured_at` de moins de `MIN_RESEND_SECONDS = 3600` avant la sienne; les lignes écartées sont marquées envoyées pour ne pas s'accumuler); `mark_sent(connection, row_ids: Sequence[int], moment: str) -> None`; `insert_remote(connection, readings: Sequence[Mapping[str, object]], moment: str) -> int` (insère avec `origin = 'remote'`, `synced_at = moment`, `source_key_id = reading["key_id"]`, `captured_at = reading["observed_at"]`, `INSERT OR IGNORE`, renvoie le nombre de lignes réellement ajoutées); `get_state(connection, name: str) -> str | None`; `set_state(connection, name: str, value: str) -> None`.

- [ ] **Étape 1: tests qui échouent**: `test_pending_returns_unsent_local_rows_oldest_first_up_to_limit`; `test_pending_ignores_remote_and_sent_rows`; `test_unchanged_price_within_an_hour_is_skipped_and_marked_sent`; `test_unchanged_price_after_an_hour_is_sent`; `test_changed_price_is_sent_at_once`; `test_mark_sent_sets_synced_at`; `test_insert_remote_adds_rows_with_remote_origin_synced_at_and_source_key_id`; `test_insert_remote_ignores_known_rows_and_counts_new_ones`; `test_state_roundtrip_and_default_none`; `test_remote_rows_appear_in_latest_prices_and_history` (via `PriceStore`).
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter** (SQL paramétré, une transaction par fonction d'écriture, dates `YYYY-MM-DDTHH:MM:SSZ`, comparaison d'une heure avec `strftime('%s', ...)`).
- [ ] **Étape 4: tests verts.**
- [ ] **Étape 5: commit** `feat: sync store (pending readings, remote insertion with the sender id, state)`.

### Tâche 8: appels réseau de la synchro (client)

**Fichiers:**
- Modifier: `src/opendofusdata/https_json.py` (paramètre `max_response_bytes`)
- Créer: `src/opendofusdata/sync_api.py`
- Tester: `tests/test_https_json.py`, `tests/test_sync_api.py`

**Interfaces:**
- Produit: `request_json(..., max_response_bytes: int = MAX_RESPONSE_BYTES)`; dans `sync_api.py`: `SYNC_MAX_RESPONSE_BYTES = 1_048_576`, `SYNC_PAGE_SIZE = 2000`, `class SyncFailure(Exception)` avec `refused: bool` (vrai pour 401) et un message en français sans clé; `push_readings(base_url: str, key: str, readings: Sequence[PendingReading]) -> int` (`POST /readings`, renvoie le nombre accepté); `pull_changes(base_url: str, key: str, since: int) -> tuple[list[dict[str, object]], int]` (`GET /readings?since=N&limit=2000`, renvoie relevés et `next`); `pull_latest_page(base_url: str, key: str, after: int) -> LatestPage` (`GET /readings/latest?after=K&limit=2000`), `LatestPage(readings, next, as_of, done)`.

- [ ] **Étape 1: tests qui échouent**: `test_request_json_accepts_a_larger_cap_when_asked` et `test_request_json_default_cap_is_unchanged` (opener factice); `test_push_sends_the_wire_format_and_returns_accepted` (corps exact: `server`, `item_id`, `lot_size`, `price`, `observed_at` = `captured_at`, rien d'autre; jeton `Bearer` de la clé); `test_pull_changes_builds_the_query_and_reads_next`; `test_latest_page_parses_done_and_as_of`; `test_401_raises_a_refused_failure`; `test_network_failure_raises_a_non_refused_failure`; `test_unexpected_body_raises_a_failure`; `test_the_key_never_appears_in_failure_messages`.
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter** en réutilisant `request_json` et `FAILURE_MESSAGES`.
- [ ] **Étape 4: tests verts.**
- [ ] **Étape 5: commit** `feat: sync network calls (push, changes, latest page)`.

### Tâche 9: moteur de synchro (client)

**Fichiers:**
- Créer: `src/opendofusdata/sync_engine.py`
- Tester: `tests/test_sync_engine.py`

**Interfaces:**
- Consomme: tâches 6 à 8.
- Produit: `class SyncOptions(NamedTuple): base_url: str; key: str; send: bool; receive: bool`; `class SyncOutcome(NamedTuple): sent: int; received: int; refused: bool; message: str`; `sync_once(connection: sqlite3.Connection, options: SyncOptions, clock: Callable[[], datetime] = utc_now) -> SyncOutcome`; `STATE_CURSOR = "cursor"`, `STATE_LATEST_DONE = "latest_done"`.
  Comportement: si `send`, envoie par lots de `SYNC_PAGE_SIZE` jusqu'à épuisement (`mark_sent` seulement après un envoi réussi); si `receive`, premier passage par `pull_latest_page` page par page (puis `latest_done = "1"` et `cursor = as_of`), ensuite `pull_changes` page par page depuis `cursor` jusqu'à une page vide, en mémorisant `cursor` après chaque page insérée. Un `401` renvoie `refused=True` sans autre appel. Une erreur réseau garde l'état déjà acquis et renvoie un message.

- [ ] **Étape 1: tests qui échouent** (les trois appels réseau sont remplacés par un double simple écrit dans le test; le client n'importe jamais de code de `src/server`): `test_nothing_is_sent_or_pulled_when_both_options_are_off`; `test_send_pushes_pending_rows_in_batches_and_marks_them_sent`; `test_failed_push_leaves_rows_unsent`; `test_receive_runs_latest_then_changes_and_stores_remote_rows_with_sender_ids`; `test_cursor_is_saved_after_each_page`; `test_second_run_pulls_only_new_changes`; `test_401_stops_everything_and_reports_refused`; `test_network_error_keeps_the_progress_made`; `test_received_rows_are_not_sent_back`.
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter** en petites fonctions (`_send_all`, `_receive_latest`, `_receive_changes`).
- [ ] **Étape 4: tests verts** et suite client.
- [ ] **Étape 5: commit** `feat: sync engine (send, latest page, changes)`.

### Tâche 10: réglages d'envoi et de récupération, fil d'arrière-plan

**Fichiers:**
- Créer: `src/opendofusdata/sync_options.py`, `src/opendofusdata/sync_worker.py`
- Modifier: `src/opendofusdata/sync_settings_card.py`, `src/opendofusdata/window_command.py`
- Tester: `tests/test_sync_options.py`, `tests/test_sync_worker.py`, `tests/test_sync_settings_card.py`

**Interfaces:**
- Consomme: `SyncOptions`, `sync_once` (tâche 9), `load_sync_key`, `resolve_server_url`.
- Produit: dans `sync_options.py`: `SYNC_SEND_KEY = "sync_send"`, `SYNC_RECEIVE_KEY = "sync_receive"`, `sync_send_enabled(config) -> bool`, `sync_receive_enabled(config) -> bool` (faux par défaut ou si la valeur n'est pas un booléen), `config_with_sync_send(config, enabled)`, `config_with_sync_receive(config, enabled)`, `load_sync_options(config_path: Path, env_path: Path) -> SyncOptions | None` (None sans clé, sans adresse, ou si les deux réglages sont faux); dans `sync_worker.py`: `SYNC_INTERVAL_SECONDS = 300`, `MAX_BACKOFF_SECONDS = 3600`, `class SyncWorker` avec `__init__(database_path: str, load_options: Callable[[], SyncOptions | None], interval: float = SYNC_INTERVAL_SECONDS)`, `start()`, `stop()`, `status() -> str`; après un `401` le fil s'arrête et `status()` dit « Clé refusée ou révoquée »; attente doublée et plafonnée après une erreur réseau, remise à l'intervalle normal après un succès.

- [ ] **Étape 1: tests qui échouent**: options (`test_options_default_to_off`, `test_non_boolean_values_count_as_off`, `test_load_options_none_without_key_url_or_both_off`, `test_load_options_reads_the_current_config_each_time`); fil (`test_worker_runs_sync_once_per_interval_with_current_options`, `test_worker_does_nothing_when_options_are_none`, `test_worker_stops_after_a_refused_key`, `test_worker_backs_off_after_network_errors_and_recovers`, `test_stop_ends_the_thread_quickly`; moteur et horloge injectés); carte (`test_card_has_two_unchecked_send_and_receive_boxes`, `test_boxes_are_disabled_without_key_or_server`, `test_ticking_a_box_saves_the_setting`, `test_card_shows_the_worker_status`).
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter**: cases « Envoyer mes prix » et « Récupérer les prix des autres » dans `SyncSettingsCard` (module sous 200 lignes, sinon extraire un cadre dans un module à part); `SyncWorker` ouvre sa propre connexion SQLite dans son fil; `window_command` crée le fil au lancement de la fenêtre (`load_options` relit la config à chaque tour) et l'arrête à la fermeture.
- [ ] **Étape 4: tests verts** et suite client complète.
- [ ] **Étape 5: commit** `feat: send and receive settings and the background sync worker`.

### Tâche 11: révocation avec ou sans suppression des relevés (administration)

**Fichiers:**
- Modifier: `src/opendofusdata/admin_client.py`, `src/opendofusdata/page_admin.py` (et `admin_rows.py` si le bouton y vit)
- Tester: `tests/test_admin_client.py`, `tests/test_page_admin.py`

**Interfaces:**
- Consomme: `POST /admin/revoke` avec `purge` (tâche 4).
- Produit: `revoke_key(base_url: str, secret: str, key_id: str, purge: bool = False) -> RevokeResult` (envoie `{"key_id": ..., "purge": purge}`); `RevokeResult.message` dit « Clé révoquée » ou « Clé révoquée, ses relevés sont supprimés » (n'affiche pas de nombre inventé: utilise `purged` de la réponse); l'onglet propose, pour une clé, deux actions distinctes: *Révoquer* et *Révoquer et supprimer ses relevés*, chacune avec sa confirmation en français; le registre marque la clé révoquée dans les deux cas, seulement après la réponse `200`.

- [ ] **Étape 1: tests qui échouent**: `test_revoke_key_sends_purge_false_by_default_and_true_when_asked`; `test_revoke_message_mentions_the_purge_when_readings_were_deleted`; `test_revoke_with_purge_marks_the_entry_revoked_only_after_200`; `test_page_offers_both_revocation_choices_with_their_own_confirmation`; `test_cancelled_confirmation_sends_nothing`.
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter** (garder `revoke_key` compatible avec les appels existants).
- [ ] **Étape 4: tests verts** et suite client complète.
- [ ] **Étape 5: commit** `feat: revoke with or without deleting the key readings from the Administration tab`.

### Tâche 12: purge locale des relevés de plus de 7 jours

**Fichiers:**
- Créer: `src/opendofusdata/local_purge.py`, `src/opendofusdata/purge_options.py`, `src/opendofusdata/local_data_card.py`
- Modifier: `src/opendofusdata/page_settings.py` (ajout de la carte), `src/opendofusdata/window_command.py` (purge au lancement si le réglage est actif)
- Tester: `tests/test_local_purge.py`, `tests/test_purge_options.py`, `tests/test_local_data_card.py`

**Interfaces:**
- Produit: dans `local_purge.py`: `LOCAL_RETENTION_DAYS = 7`, `class PurgeResult(NamedTuple): lot_prices: int; market_stats: int`, `purge_old_readings(connection: sqlite3.Connection, now: datetime) -> PurgeResult` (supprime les lignes de `lot_prices` dont `captured_at` précède `now - 7 jours`, sauf la plus récente de chaque (`item_id`, `server`, `lot_size`) selon `captured_at` puis `id`; idem pour `market_stats` par (`item_id`, `server`, `period`); l'origine et `synced_at` sont ignorés; aucune autre table n'est touchée); dans `purge_options.py`: `PURGE_KEY = "purge_old_data"`, `purge_enabled(config) -> bool` (faux par défaut ou si la valeur n'est pas un booléen), `config_with_purge(config, enabled)`; dans `local_data_card.py`: `LocalDataCard` (case « Supprimer automatiquement les relevés de plus de 7 jours (au lancement) » et bouton « Purger maintenant » avec confirmation en français, tâche en arrière-plan via `BackgroundTask`, message du résultat: nombre de lignes supprimées).

- [ ] **Étape 1: tests qui échouent**: purge (`test_old_rows_are_deleted_but_the_latest_of_each_key_is_kept`, `test_rows_within_seven_days_are_kept`, `test_the_boundary_is_exactly_seven_days`, `test_remote_and_local_rows_are_treated_alike`, `test_market_stats_follow_the_same_rule_per_item_server_period`, `test_other_tables_are_untouched` (favoris de familiers, observations manuelles, noms d'objets, serveurs, brisages, améliorations de familiers, état de synchro: contenu identique avant et après), `test_purge_twice_deletes_nothing_more`, `test_result_counts_deleted_rows`); réglage (`test_option_defaults_to_off`, `test_non_boolean_value_counts_as_off`, `test_config_with_purge_roundtrip`); carte (`test_card_has_an_unchecked_automatic_box_and_a_purge_button`, `test_ticking_the_box_saves_the_setting`, `test_purge_button_asks_for_confirmation_and_cancel_deletes_nothing`, `test_purge_button_runs_in_the_background_and_shows_the_count`); lancement (`test_startup_purges_only_when_enabled`).
- [ ] **Étape 2: constater l'échec.**
- [ ] **Étape 3: implémenter** (SQL paramétré avec `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY captured_at DESC, id DESC)`, une transaction; la carte vit dans son propre module pour garder `page_settings.py` sous 200 lignes; au lancement de la fenêtre, la purge tourne dans un fil avec sa propre connexion).
- [ ] **Étape 4: tests verts** et suite client complète.
- [ ] **Étape 5: commit** `feat: optional local purge of readings older than 7 days (latest price per key and user data kept)`.

### Tâche 13: documentation, confidentialité et consignes

**Fichiers:**
- Modifier: `README.md`, `docs/developpement.md`, `docs/roadmap.md`, `CLAUDE.md`, `docs/superpowers/specs/2026-11-16-player-sync-design.md`, `src/opendofusdata/settings_about.py` si le résumé cite la synchro

- [ ] **Étape 1:** README: la bannière « Online sync is coming later » devient une description honnête (envoi et récupération des prix de lots de l'HDV, désactivés par défaut, activables dans Réglages); la section Privacy dit exactement ce qui part (prix de lots, taille du lot, identifiant d'objet, nom du serveur de jeu choisi, date d'observation, plus la clé dans l'en-tête), que le code de 11 caractères de ta clé accompagne tes relevés et est visible par les autres joueurs (un pseudonyme, sans lien avec ton compte ni ton personnage), que ni adresse IP, ni compte, ni nom de personnage ne sont envoyés ni conservés, et que le serveur garde 7 jours de relevés.
- [ ] **Étape 2:** `docs/developpement.md`: sous-section « Synchronisation des prix » (purge locale optionnelle et ce qu'elle ne touche jamais, routes REST, paramètres autorisés, format, curseur, instantané, rétention de 7 jours, `key_id` des relevés, révocation avec ou sans purge, réglages, fil d'arrière-plan).
- [ ] **Étape 3:** `docs/roadmap.md` (fait / reste: statistiques de marché, brisage, familiers, médiane, propagation de la purge aux clients) et `CLAUDE.md` (le client envoie des prix de lots sur réglage explicite; toujours aucune adresse collectée).
- [ ] **Étape 4:** corriger la spécification: routes REST (décision 1), révocation avec option de purge (décision 2), identité de la clé gardée avec les relevés.
- [ ] **Étape 5: tests:** `.venv/Scripts/python.exe -m pytest -q tests/test_text_style.py`, suite client complète, suite serveur complète; attendu: tout passe.
- [ ] **Étape 6: commit** `docs: price synchronisation (README privacy, developer guide, roadmap, CLAUDE.md, spec updates)`.

## Vérification finale

- Suite serveur et suite client vertes.
- Essai de bout en bout local: `uvicorn` du serveur avec `KEYSERVER_ALLOWED_HOSTS=127.0.0.1,localhost` et deux clés; vérifier à la main un envoi, une récupération (avec `key_id`), une révocation sans purge puis avec purge.
