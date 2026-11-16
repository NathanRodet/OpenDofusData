# Serveur de clés d'API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un petit serveur dans `src/server/` qui n'accepte que les requêtes portant une clé signée valide et non révoquée; dans OpenDofusData, un onglet Administration (visible seulement avec le secret dans `.env`) qui génère les clés en local et les révoque, et, pour les joueurs, un champ "clé de synchronisation" dans les Réglages avec un bouton "Tester la connexion".

**Architecture:** Les clés sont des jetons signés `odk1.<identifiant>.<signature>` (HMAC-SHA256 de l'identifiant avec un secret maître). L'administrateur les génère sur son PC sans appel réseau, le serveur les vérifie sans rien stocker, et seule la révocation touche le serveur: une table d'identifiants révoqués et une route `POST /admin/revoke`. L'administration s'authentifie avec un jeton dérivé du secret (le secret maître ne circule jamais). Trois middlewares ASGI protègent le serveur dans cet ordre: limite de taille, authentification Bearer, format de la requête. Le joueur colle sa clé dans les Réglages; "Tester la connexion" appelle `GET /check`. L'ingestion des relevés est hors de ce plan.

**Tech Stack:** Python 3.13, sqlite3, hmac, hashlib, secrets, argparse (stdlib); FastAPI (Pydantic v2) + uvicorn + httpx (tests) pour le serveur, dans un venv et un lock séparés du client; côté client `urllib` seulement (aucune dépendance nouvelle).

**Spec:** aucune spec écrite; les décisions viennent de la conversation du 2026-11-15 (clés distribuées à la main, génération locale par HMAC avec un secret dans `.env`, révocation par liste noire sur le serveur, en-tête RFC 6750, saisie et test de la clé dans l'interface du joueur, serveur dans `src/server/`).

## Global Constraints

- Règles de CLAUDE.md: fonctions de 20 lignes maximum, modules de 200 lignes maximum, annotations de type sur toutes les signatures, docstring courte sur les fonctions publiques, pas de nombres magiques, noms anglais explicites, pas d'`except:` nu, logs via `logging`, tests `pytest` sur données synthétiques.
- Format de clé: `KEY_PATTERN = r"^odk1\.[A-Za-z0-9_-]{11}\.[A-Za-z0-9_-]{43}$"`; identifiant de 8 octets aléatoires, signature `HMAC-SHA256(secret, "odk1." + identifiant)` (32 octets), les deux en base64 URL sans remplissage.
- Secret maître: `secrets.token_urlsafe(32)` (43 caractères), au moins `MIN_SECRET_LENGTH = 43`; le serveur refuse de démarrer sans secret valide. Jeton d'administration: base64 URL de `HMAC-SHA256(secret, "odk1-admin")`, jamais le secret lui-même.
- Le même secret est dans `src/server/.env` (`KEY_SECRET`) et dans le `.env` de l'administrateur (`ADMIN_SECRET`). Il n'est jamais dans l'exécutable, `config.json`, les logs ni une exception.
- En-tête: `Authorization: Bearer <valeur>`; refus: `401` avec `WWW-Authenticate: Bearer`, même réponse pour valeur absente, mal formée, mal signée ou révoquée.
- Domaines d'authentification: `/admin/` n'accepte que le jeton d'administration, tous les autres chemins que les clés; aucun des deux n'est accepté chez l'autre.
- Liste blanche stricte: seules les paires (méthode, chemin) de `ALLOWED_ROUTES` passent; corps limité à `MAX_BODY_BYTES = 1_048_576`; un corps exige `Content-Type: application/json`; une chaîne de requête non prévue est refusée.
- Ordre des contrôles dans l'application: taille, authentification, format. Pour tout chemin déclaré, un appel sans identifiant valide donne `401` (les routes sont publiques dans le dépôt, leur existence n'est pas un secret).
- Champs validés par Pydantic en mode strict avec `extra="forbid"`; tout texte refuse les caractères de contrôle; l'injection SQL est évitée par des requêtes paramétrées, pas par un filtrage de caractères. Comparaisons secrètes avec `hmac.compare_digest`; aucune valeur d'en-tête dans les logs ni les erreurs.
- Client: aucune requête réseau sans action explicite (bouton "Tester la connexion", ou action de l'onglet Administration); HTTPS seulement, sans suivre de redirection, délai court, taille de réponse bornée; sans clé enregistrée ni secret, rien ne part.
- Le serveur (`src/server/`) n'importe rien de `src/opendofusdata` et inversement; le paquet client publié ne contient pas le serveur. Les petites fonctions communes (format de clé, HMAC) sont recopiées des deux côtés et verrouillées par un même vecteur de test dans les deux suites.
- Aucun tiret cadratin, demi-cadratin, signe moins ni point médian dans les textes (tests/test_text_style.py).
- `.env`, la base du serveur et `admin_keys.json` ne sont jamais versionnés; `.env.example` l'est.

## Review Focus

- Clé modifiée d'un caractère, tronquée, avec un autre préfixe, ou signée par un autre secret: `401`, jamais `500`.
- Clé révoquée puis reprise: reste refusée, y compris après redémarrage; révoquer deux fois est sans effet.
- En-tête mal formé (`Bearer` sans valeur, `Basic`, plusieurs espaces, valeur vide): `401`.
- Secret serveur absent, vide ou trop court: le serveur ne démarre pas (jamais d'accès ouvert par défaut).
- Jeton d'administration présenté sur `/check`, ou clé joueur présentée sur `/admin/revoke`: `401`.
- Corps trop gros (en-tête géant ou flux sans longueur): `413` sans tout lire en mémoire.
- Variantes de chemin (`/check/`, `//check`, `/CHECK`, `/check?x=1`, `/check%2F`): refusées, jamais normalisées.
- Champs texte avec saut de ligne, octet nul, apostrophe, point-virgule, chevron ou espace initial: `422`; champ inconnu ou mauvais type: `422`; lot vide ou trop grand, date hors fenêtre: `422`.
- Client, Réglages: clé collée avec espaces ou retour à la ligne (nettoyée), clé au mauvais format (refusée avant tout envoi), serveur injoignable, délai dépassé, réponse non JSON, redirection: message clair, jamais de plantage; la clé n'est ni affichée en clair par défaut ni écrite dans les logs.
- Client, Administration: révocation qui échoue (réseau coupé): le registre local reste inchangé; registre absent ou corrompu: démarrage avec une liste vide, pas de plantage.
- `.env` absent, vide, avec guillemets, commentaires ou lignes sans `=`: lu sans erreur; valeur absente donne `None`, pas une chaîne vide.
- Certificat absent au premier démarrage ou non rechargé après renouvellement; port de l'application joignable de l'extérieur; routes `/admin/` martelées.
- Client qui envoie un `Host` forgé, `X-Forwarded-For`, `Cookie`, `Forwarded`, `X-HTTP-Method-Override` ou `Upgrade`: aucun n'atteint l'application tel quel.

---

### Task 1: Secret d'administration et adresse du serveur dans un `.env` non versionné

**Files:**
- Create: `src/opendofusdata/env_file.py`, `.env.example`
- Modify: `.gitignore`
- Test: `tests/test_env_file.py`

**Interfaces:**
- Produces: `read_env_file(path: Path) -> dict[str, str]`; `admin_secret(path: Path) -> str | None` (`ADMIN_SECRET_NAME = "ADMIN_SECRET"`, `None` si absent, vide ou plus court que `MIN_SECRET_LENGTH = 43`); `server_url_override(path: Path) -> str | None` (`SERVER_URL_NAME = "SERVER_URL"`), qui n'accepte que `https://hôte[:port]` sans chemin, requête, fragment ni identifiants, retire une barre finale, et renvoie sinon `None` avec un avertissement (jamais la valeur du secret).
- Le `.env` du client est à côté de `config.json`.

- [ ] **Step 1: Write the failing tests** dans `tests/test_env_file.py`:
  - `test_reads_plain_and_quoted_values` (`A=1`, `B="deux"`, `C='trois'`).
  - `test_ignores_comments_blank_and_malformed_lines`.
  - `test_missing_file_gives_empty_dict`.
  - `test_admin_secret_is_none_when_absent_blank_or_too_short_and_returns_a_valid_one`.
  - `test_server_url_accepts_https_and_strips_the_trailing_slash` (`https://exemple.fr/` donne `https://exemple.fr`; `https://exemple.fr:8443` accepté).
  - `test_server_url_rejects_http_paths_queries_credentials_and_garbage` (`http://h`, `https://h/chemin`, `https://h?x=1`, `https://u:p@h`, `ftp://h`, `exemple.fr`, chaîne vide: tous `None`).
  - `test_gitignore_excludes_env_but_not_the_example`.
- [ ] **Step 2: Run** `.\dev.ps1 test` filtré sur ce fichier: échec.
- [ ] **Step 3: Implement** `env_file.py`: lecture UTF-8, `OSError` journalisé en avertissement et traité comme fichier absent, coupure sur le premier `=`, valeur nettoyée des espaces puis d'une paire de guillemets; `server_url_override` s'appuie sur `urllib.parse`.
- [ ] **Step 4: Ajouter** `.env`, `admin_keys.json` au `.gitignore`; créer `.env.example` avec `ADMIN_SECRET=` et `SERVER_URL=` et un commentaire par ligne (secret réservé à l'administrateur; adresse HTTPS du serveur si elle diffère de celle par défaut).
- [ ] **Step 5: Run** la suite complète: tout passe, y compris `test_text_style`.
- [ ] **Step 6: Commit** `feat: read the admin secret and server URL from a git-ignored .env`

---

### Task 2: Clés signées et liste des révocations (serveur, stdlib seulement)

**Files:**
- Create: `src/server/pytest.ini` (`pythonpath = .`, `testpaths = tests`; les tests du serveur se lancent depuis `src/server`)
- Modify: `pyproject.toml` (`[tool.setuptools.packages.find]` avec `include = ["opendofusdata*"]`)
- Create: `src/server/keyserver/__init__.py`, `src/server/keyserver/signed_keys.py`, `src/server/keyserver/revocations.py`
- Test: `src/server/tests/test_signed_keys.py`, `src/server/tests/test_revocations.py`, `tests/test_package_layout.py` (`test_client_package_excludes_the_server`, `test_server_does_not_import_the_client`)

**Interfaces:**
- Produces dans `signed_keys.py`: `KEY_PATTERN`, `MIN_SECRET_LENGTH = 43`, `generate_secret() -> str`, `make_key(secret: str, key_id: str) -> str`, `new_key_id() -> str`, `parse_key(key: str) -> str | None` (renvoie l'identifiant si le format est strict, sinon `None`), `signature_is_valid(secret: str, key: str) -> bool` (`compare_digest`), `admin_token(secret: str) -> str`.
- Produces dans `revocations.py`: `class RevocationStore(connection: sqlite3.Connection)` avec `revoke(key_id: str) -> None` (sans effet si déjà révoquée), `is_revoked(key_id: str) -> bool`; `open_revocations(path: Path) -> RevocationStore` crée la table `revoked_keys(key_id TEXT PRIMARY KEY, revoked_at TEXT)`.
- Vecteur fixe pour tester la compatibilité avec le client: secret `"A" * 43`, identifiant `"AAAAAAAAAAA"`; la clé et le jeton attendus sont calculés une fois à l'implémentation et recopiés tels quels dans `tests/test_admin_keys.py` du client.

- [ ] **Step 1: Write the failing tests:**
  - `test_generated_secret_is_long_enough_and_distinct`.
  - `test_made_key_matches_the_pattern_and_verifies`.
  - `test_tampered_truncated_wrongly_prefixed_or_differently_signed_keys_fail` (un caractère changé dans l'identifiant, dans la signature, clé coupée, préfixe `odk2`, autre secret, chaîne vide, 10 000 caractères).
  - `test_parse_key_is_strict` (`None` pour tout ce qui ne colle pas à `KEY_PATTERN`, y compris saut de ligne final).
  - `test_admin_token_differs_from_the_secret_and_from_any_key`.
  - `test_known_vector` (clé et jeton attendus, figés).
  - `test_revoke_is_idempotent_and_survives_reopening_the_file` (base sur fichier `tmp_path`).
  - `test_unknown_id_is_not_revoked`.
- [ ] **Step 2: Run** `pytest` lancé depuis `src/server`: échec.
- [ ] **Step 3: Implement** `signed_keys.py` puis `revocations.py`; horodatage UTC ISO via `datetime.now(timezone.utc)`.
- [ ] **Step 4: Run** `pytest` lancé depuis `src/server` puis la suite du client: tout passe.
- [ ] **Step 5: Commit** `feat(server): signed API keys and revocation list`

---

### Task 3: Configuration du serveur et génération du secret

**Files:**
- Create: `src/server/keyserver/settings.py`, `src/server/keyserver/__main__.py`
- Modify: `.gitignore` (`src/server/keys.db`, `src/server/.env`, `src/server/.venv/`)
- Test: `src/server/tests/test_settings.py`

**Interfaces:**
- Consumes: `MIN_SECRET_LENGTH`, `generate_secret` (Task 2).
- Produces: `class Settings(db_path: Path, key_secret: str)` et `load_settings(environ: Mapping[str, str]) -> Settings` (variables `KEY_SECRET`, et `KEYSERVER_DB` avec défaut `src/server/keys.db`); lève `SettingsError` si le secret manque ou est trop court. `main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int` pour `python -m keyserver new-secret`: imprime une seule fois `KEY_SECRET=<secret>` (pour le `.env` du serveur) et `ADMIN_SECRET=<secret>` (pour le `.env` de l'administrateur).

- [ ] **Step 1: Write the failing tests:** `test_secret_missing_blank_or_too_short_raises` ; `test_valid_environment_gives_settings_with_the_default_database_path` ; `test_new_secret_command_prints_both_lines_with_the_same_valid_secret_and_returns_0` ; `test_unknown_subcommand_is_refused`.
- [ ] **Step 2: Run** `pytest` depuis `src/server`: échec. **Step 3: Implement** (argparse, une seule sous-commande). **Step 4: Run:** tout passe.
- [ ] **Step 5: Commit** `feat(server): settings that refuse to start without a secret, new-secret command`

---

### Task 4: Application HTTP avec authentification Bearer

**Files:**
- Create: `src/server/requirements.txt`, `src/server/requirements.lock` (pip-compile avec hashes), `src/server/dev.ps1` (`setup`, `test`, `run`, `new-secret`; venv `src/server/.venv`)
- Create: `src/server/keyserver/auth.py`, `src/server/keyserver/app.py`
- Test: `src/server/tests/test_auth.py`

**Interfaces:**
- Consumes: `parse_key`, `signature_is_valid` (Task 2), `RevocationStore`, `Settings` (Task 3).
- Produces: `bearer_token(header: str | None) -> str | None` (pur); `class KeyVerifier(secret: str, revocations: RevocationStore)` avec `is_valid(key: str) -> bool`; `create_app(settings: Settings, revocations: RevocationStore) -> FastAPI` avec `GET /check` (`200 {"status": "ok"}`); `BearerAuthMiddleware(app, verifier)` répond `401` + `WWW-Authenticate: Bearer` (`{"detail": "unauthorized"}`) sinon.

- [ ] **Step 1: Write the failing tests** (`TestClient`, secret et magasin de test):
  - `test_bearer_token_parsing` (`"Bearer abc"` donne `"abc"`; `None`, `""`, `"Bearer"`, `"Bearer "`, `"Basic abc"`, `"Bearer a b"` donnent `None`; schéma insensible à la casse).
  - `test_valid_key_gets_200`.
  - `test_missing_malformed_tampered_and_revoked_keys_get_the_same_401`.
  - `test_revoking_takes_effect_on_the_next_request_without_restart`.
  - `test_the_key_never_appears_in_the_logs` (caplog).
- [ ] **Step 2: Run** `src\server\dev.ps1 test`: échec.
- [ ] **Step 3: Implement** `auth.py` (parsing et middleware) et `app.py`; désactiver le journal d'accès d'uvicorn s'il affiche les en-têtes.
- [ ] **Step 4: Générer** le lock avec `pip-compile --generate-hashes --allow-unsafe --strip-extras`, installer avec `--require-hashes`, relancer les tests: tout passe.
- [ ] **Step 5: Documenter** dans `docs/developpement.md` une section "Serveur de clés" (commande `new-secret`, lancement, emplacement du `.env`, rôle des onglets), sans caractères interdits.
- [ ] **Step 6: Commit** `feat(server): bearer-authenticated app and server dev script`

---

### Task 5: Middlewares de limite et de format

**Files:**
- Create: `src/server/keyserver/request_rules.py` (logique pure), `src/server/keyserver/guards.py` (middlewares ASGI purs)
- Modify: `src/server/keyserver/app.py` (empilement: limite de taille, authentification, format)
- Test: `src/server/tests/test_request_rules.py`, `src/server/tests/test_guards.py`

**Interfaces:**
- Produces dans `request_rules.py`: `MAX_BODY_BYTES = 1_048_576`, `ALLOWED_ROUTES: dict[str, frozenset[str]]` (au départ `{"/check": frozenset({"GET"})}`), `JSON_TYPE = "application/json"`, `class Rejection(status: int, detail: str, allow: str | None)`, `check_format(method: str, path: str, query: bytes, content_type: str | None, has_body: bool) -> Rejection | None`.
- Produces dans `guards.py`: `BodyLimitMiddleware(app, max_bytes: int)` (`413`) et `RequestFormatMiddleware(app)` (`404`, `405` avec `Allow`, `400` pour chaîne de requête non prévue, `415` pour un corps non JSON); réponses JSON génériques `{"detail": "..."}`.

- [ ] **Step 1: Write the failing tests** pour `check_format`: route et méthode autorisées passent; chemin inconnu `404`; mauvaise méthode `405` avec `Allow`; variantes (`/check/`, `//check`, `/CHECK`, `/check%2F`, `/check/..`, chemin vide) toutes refusées; chaîne de requête inattendue `400`; corps sans JSON `415`; `application/json; charset=utf-8` accepté, casse ignorée.
- [ ] **Step 2: Write the failing tests** pour les middlewares (`TestClient`, clé valide): `Content-Length` géant `413` avant lecture; flux sans longueur au-dessus de la limite `413`; sans clé, tout chemin et toute méthode donnent `401` (sauf `413`); avec clé, chemin inconnu `404` et méthode non prévue `405` avec `Allow`; les réponses ne répètent rien de la requête; une requête valide atteint la route.
- [ ] **Step 3: Run** `src\server\dev.ps1 test`: échec. **Step 4: Implement** (chemin brut comparé exactement, aucune normalisation; compteur d'octets en enveloppant `receive`, pas de `BaseHTTPMiddleware`). **Step 5: Empiler** dans `create_app` et vérifier l'ordre par test. **Step 6: Run:** tout passe.
- [ ] **Step 7: Commit** `feat(server): body limit and strict request format middlewares`

---

### Task 6: Schémas stricts des relevés

**Files:**
- Create: `src/server/keyserver/schemas.py`
- Test: `src/server/tests/test_schemas.py`

**Interfaces:**
- Produces: `MAX_BATCH_READINGS = 2000`, `MAX_SERVER_NAME_LENGTH = 40`, `MAX_ITEM_ID = 10_000_000`, `EARLIEST_OBSERVATION = datetime(2020, 1, 1, tzinfo=UTC)`, `FUTURE_TOLERANCE = timedelta(minutes=5)`, `SERVER_NAME_PATTERN = r"^[^\W_][\w -]{0,39}$"`; `utc_now() -> datetime`; `class Reading(BaseModel)` (`extra="forbid"`, `strict=True`) avec `server: str`, `item_id: int`, `observed_at: datetime` (avec fuseau, entre `EARLIEST_OBSERVATION` et maintenant plus `FUTURE_TOLERANCE`); `class ReadingBatch(BaseModel)` avec `readings: list[Reading]` (1 à `MAX_BATCH_READINGS`). Les champs propres à chaque catégorie viendront avec l'ingestion.
- Mes choix, à confirmer: le nom de serveur commence par une lettre (accents compris) ou un chiffre, puis lettres, chiffres, espace, tiret ASCII, souligné; 40 caractères au plus.

- [ ] **Step 1: Write the failing tests:** relevé valide (`Brâkmar`, `Pandala-1`); champ inconnu refusé; types erronés (texte, `True`, `"12"`, date sans fuseau); nom de serveur refusant saut de ligne, octet nul, apostrophe, point-virgule, `<b>`, espace initial, vide, 41 caractères; bornes de `item_id`; fenêtre de dates; bornes du lot (0, 2000, 2001).
- [ ] **Step 2: Run:** échec. **Step 3: Implement** avec Pydantic v2 (`ConfigDict(extra="forbid", strict=True)`). **Step 4: Run:** tout passe.
- [ ] **Step 5: Commit** `feat(server): strict reading schemas`

---

### Task 7: Route de révocation (serveur)

**Files:**
- Create: `src/server/keyserver/admin_routes.py`
- Modify: `src/server/keyserver/auth.py` (second domaine: jeton d'administration pour `/admin/`), `src/server/keyserver/app.py`, `src/server/keyserver/request_rules.py` (`ALLOWED_ROUTES`), `src/server/keyserver/schemas.py`
- Test: `src/server/tests/test_admin_routes.py`

**Interfaces:**
- Consumes: `admin_token` (Task 2), `RevocationStore.revoke` (Task 2), `create_app` (Task 4).
- Produces: `POST /admin/revoke` avec `{"key_id": str}`: `200 {"revoked": true}` (idempotent, même si l'identifiant n'a jamais été émis); `class KeyIdRequest(BaseModel)` (`extra="forbid"`, `strict=True`, `key_id` de exactement 11 caractères `[A-Za-z0-9_-]`). Journal: une ligne avec l'identifiant révoqué, jamais le jeton.

- [ ] **Step 1: Write the failing tests:** sans en-tête, avec un mauvais jeton, avec une clé joueur valide, avec le secret maître lui-même: `401` identiques; le jeton d'administration sur `/check`: `401`; révocation puis `GET /check` avec la clé correspondante: `401` aussitôt; révoquer deux fois: `200` les deux fois; corps invalides (`key_id` vide, trop long, caractère interdit, champ inconnu, type erroné): `422`; `DELETE /admin/revoke` `405` avec `Allow`, `/admin/revoke/` `404`, corps non JSON `415`; ni la clé, ni le jeton, ni le secret dans les logs.
- [ ] **Step 2: Run:** échec. **Step 3: Implement** la route, le second domaine d'authentification (choix par préfixe de chemin) et l'entrée dans `ALLOWED_ROUTES`. **Step 4: Run:** tout passe.
- [ ] **Step 5: Commit** `feat(server): admin route to revoke a key`

---

### Task 8: Réglages du joueur: clé de synchronisation et test de connexion

**Files:**
- Create: `src/opendofusdata/https_json.py` (requête JSON HTTPS commune), `src/opendofusdata/sync_key.py` (format et stockage de la clé), `src/opendofusdata/sync_client.py` (test de connexion), `src/opendofusdata/sync_settings_card.py` (carte d'interface)
- Modify: `src/opendofusdata/page_settings.py` (ajoute la carte "Synchronisation"), `README.md`, `docs/developpement.md`
- Test: `tests/test_https_json.py`, `tests/test_sync_key.py`, `tests/test_sync_client.py`, `tests/test_sync_settings_card.py`

**Interfaces:**
- Produces dans `https_json.py`: `REQUEST_TIMEOUT_SECONDS = 10`, `MAX_RESPONSE_BYTES = 65_536`, `class HttpsFailure(Exception)` (avec `reason: str` parmi `unreachable`, `timeout`, `bad_response`, `redirect`), `request_json(base_url: str, method: str, path: str, token: str | None = None, body: dict | None = None, opener: OpenerDirector = OPENER) -> tuple[int, dict]` (réutilise `NoRedirectHandler` de `names_fetch.py`; n'accepte que `https://`; lit au plus `MAX_RESPONSE_BYTES`).
- Produces dans `sync_key.py`: `KEY_PATTERN` (identique à celui du serveur), `SYNC_KEY_CONFIG = "sync_api_key"`, `clean_key(text: str) -> str` (retire espaces et sauts de ligne), `key_format_ok(key: str) -> bool`, `load_sync_key(config_path: Path) -> str | None`, `save_sync_key(config_path: Path, key: str | None) -> bool` (écrit dans `config.json` comme `pet_favorites_store`, refuse un mauvais format).
- Produces dans `sync_client.py`: `DEFAULT_SERVER_URL = ""` (à renseigner quand le domaine existe; en attendant, l'adresse vient de `SERVER_URL` dans `.env`), `resolve_server_url(env_path: Path) -> str | None`, `class ConnectionResult(NamedTuple)` (`ok: bool`, `message: str`), `check_connection(base_url: str, key: str, opener=OPENER) -> ConnectionResult` qui appelle `GET /check` avec `Authorization: Bearer <clé>`: `200` donne "Connexion réussie", `401` "Clé refusée ou révoquée", panne ou délai "Serveur injoignable", autre réponse "Réponse inattendue du serveur".
- Produces dans `sync_settings_card.py`: `SyncSettingsCard` (champ masqué par `show="•"` avec case "Afficher", boutons "Enregistrer" et "Tester la connexion", message de résultat coloré). Sans adresse de serveur connue, le bouton de test est désactivé avec l'explication "Serveur de synchronisation non configuré". Le test envoie la clé du champ (même non enregistrée) et rien d'autre; il s'exécute hors du fil de l'interface.
- Cette carte est la seule action réseau des joueurs, et elle ne part que sur clic. Le README et la confidentialité le disent: l'application envoie toujours uniquement ce test, à la demande.

- [ ] **Step 1: Write the failing tests:**
  - `https_json`: réponse JSON lue; `http://` refusé avant tout envoi; redirection refusée (`HttpsFailure("redirect")`); délai, hôte injoignable, corps non JSON, corps au-dessus de `MAX_RESPONSE_BYTES`: `HttpsFailure`; l'en-tête `Authorization` n'apparaît ni dans les erreurs ni dans caplog.
  - `sync_key`: `clean_key` retire espaces, tabulations, sauts de ligne internes; `key_format_ok` strict (vecteur du serveur accepté; un caractère de trop, préfixe différent, vide: refusés); sauvegarde puis relecture; sauvegarde refusée pour un mauvais format; `None` efface la clé; fichier de configuration absent ou illisible ne plante pas.
  - `sync_client`: `200`, `401`, `500`, délai, injoignable, JSON inattendu donnent le bon `ConnectionResult`; adresse issue de `SERVER_URL` quand `DEFAULT_SERVER_URL` est vide; aucune adresse donne `None`; la clé n'est jamais dans `message`.
  - `sync_settings_card`: champ masqué par défaut et dévoilé par la case; enregistrer une clé valide la stocke, une clé invalide affiche une erreur sans rien écrire; le test de connexion affiche le message du résultat (faux client injecté); bouton désactivé sans adresse; aucune requête à la construction de la page.
- [ ] **Step 2: Run** `.\dev.ps1 test` filtré: échec. **Step 3: Implement** `https_json.py`, `sync_key.py`, `sync_client.py` puis la carte, et l'ajouter à `page_settings.py` en respectant les limites de taille (scinder si besoin).
- [ ] **Step 4: Run** la suite complète: tout passe, y compris `test_text_style`.
- [ ] **Step 5: Mettre à jour** le README (section confidentialité) et `docs/developpement.md`, sans caractères interdits.
- [ ] **Step 6: Commit** `feat: sync key field and connection test in the settings`

---

### Task 9: Onglet Administration (génération locale et révocation)

**Files:**
- Create: `src/opendofusdata/admin_keys.py` (clés et jeton), `src/opendofusdata/admin_registry.py` (registre local), `src/opendofusdata/page_admin.py`
- Modify: `src/opendofusdata/window_pages.py` et la définition du menu (`PAGE_NAMES`): la page "Administration" n'est ajoutée que si `admin_secret` est valide et qu'une adresse de serveur est connue
- Test: `tests/test_admin_keys.py`, `tests/test_admin_registry.py`, `tests/test_page_admin.py`

**Interfaces:**
- Consumes: `admin_secret`, `server_url_override` (Task 1), `request_json`, `HttpsFailure`, `resolve_server_url`, `KEY_PATTERN` (Task 8).
- Produces dans `admin_keys.py`: `new_key_id() -> str`, `make_key(secret: str, key_id: str) -> str`, `admin_token(secret: str) -> str` (recopies des fonctions du serveur, vérifiées par le même vecteur).
- Produces dans `admin_registry.py`: `class KeyEntry(NamedTuple)` (`key_id`, `label`, `created_at`, `revoked_at: str | None`), `class AdminRegistry(path: Path)` avec `entries() -> list[KeyEntry]`, `add(label: str, key_id: str) -> KeyEntry`, `mark_revoked(key_id: str) -> None`, enregistré dans `admin_keys.json` à côté du `.env` (écriture atomique; fichier absent ou corrompu donne une liste vide, journalisé). Le registre ne contient jamais de clé ni de secret: la clé se recalcule avec `make_key(secret, key_id)`.
- Produces dans `page_admin.py`: `AdminPage`: tableau (pseudo, date de création, état), champ pseudo plus bouton "Générer une clé" (la clé s'affiche avec un bouton "Copier"), bouton "Copier la clé" sur une ligne existante, bouton "Révoquer" avec confirmation: appelle `POST /admin/revoke` avec le jeton d'administration, et ne marque la ligne révoquée qu'après un `200`. Les appels réseau sont hors du fil de l'interface. Générer ne fait aucun appel réseau.

- [ ] **Step 1: Write the failing tests:** `admin_keys` (clé au bon format, vérifiée par le motif; vecteur identique à celui du serveur; deux identifiants distincts; jeton différent du secret); `admin_registry` (ajout et relecture; marquer révoqué; fichier absent, vide, JSON invalide, mauvais types: liste vide sans plantage; aucune clé dans le fichier écrit); `page_admin` (page absente sans secret valide ou sans adresse, présente avec les deux; générer ajoute une ligne sans appel réseau; copier recalcule la même clé; révoquer demande confirmation, appelle le serveur avec `Authorization: Bearer <jeton>` (et jamais le secret), marque révoqué seulement après `200`; une panne réseau laisse le registre inchangé et affiche une erreur; pseudo vide ou de plus de 60 caractères refusé).
- [ ] **Step 2: Run** `.\dev.ps1 test` filtré: échec. **Step 3: Implement** les trois modules puis l'ajout conditionnel au menu, en scindant tableau et dialogues si un module dépasse 200 lignes.
- [ ] **Step 4: Run** la suite complète: tout passe. **Step 5: Mettre à jour** `docs/developpement.md` (onglet Administration, `ADMIN_SECRET` et `SERVER_URL` dans `.env`, sauvegarde de `admin_keys.json`), sans caractères interdits.
- [ ] **Step 6: Commit** `feat: Administration tab to generate and revoke keys`

---

## Hors de ce plan

- La route d'ingestion des relevés et leur agrégation (l'identifiant de clé servira d'identifiant de contributeur, à stocker avec chaque relevé), avec la validation de leurs champs par catégorie (modèles stricts, bornes tirées des vraies données du client; elle déclarera `POST /ingest` dans `ALLOWED_ROUTES`).
- L'envoi automatique des relevés par le client (README et politique de confidentialité à mettre à jour à ce moment, avec les réglages par catégorie).
- L'hébergement, le nom de domaine et la valeur de `DEFAULT_SERVER_URL`.
- Bannissement des clients abusifs (fail2ban sur l'hôte, ou dans l'application) et pare-feu applicatif (WAF): écartés pour l'instant; à reprendre si des abus réels apparaissent.
- Journal d'audit persistant des révocations, plusieurs administrateurs, rotation du secret (à la main: nouveau secret, toutes les clés sont à regénérer).

## Self-review

- Couverture: secret et adresse dans `.env` (tâche 1), clés signées et révocations (2), configuration et refus de démarrer sans secret (3), authentification Bearer (4), liste blanche et limites (5), champs stricts (6), révocation protégée par jeton d'administration (7), clé et test de connexion pour les joueurs (8), génération locale et révocation pour l'administrateur (9), dossier `src/server/` (tâches 2 à 9).
- Cohérence des noms: `make_key`, `new_key_id`, `parse_key`, `signature_is_valid`, `admin_token`, `generate_secret`, `RevocationStore`, `KeyVerifier`, `Settings`, `load_settings`, `check_format`, `ALLOWED_ROUTES`, `KeyIdRequest`, `Reading`, `ReadingBatch`, `request_json`, `HttpsFailure`, `check_connection`, `ConnectionResult`, `AdminRegistry`, `KeyEntry`, `admin_secret`, `server_url_override`, `resolve_server_url` sont identiques entre les tâches.
- Proportion: onze tâches, chacune avec son cycle de test et un livrable testable seul; les tâches 2 et 3 n'exigent aucune dépendance nouvelle.


## Exécution: écarts par rapport au plan et limites (2026-11-15)

Le plan ci-dessus décrit l'intention; voici ce que le code fait réellement et ce qui n'a pas été vérifié.

**Écarts voulus**
- Bannissement des chemins inexistants (ancienne tâche 12): abandonné. Plus aucune adresse de joueur n'est enregistrée ni transmise: journal d'accès sans adresse, `error_log` au niveau critique, plus de `X-Forwarded-For`. Les limites de débit gardent en mémoire seulement un condensé de l'adresse comme clé de comptage.
- Tâche 3: `main(argv, out)` est dans `keyserver/cli.py` (`settings.py` reste pur). Les hôtes acceptés par l'application sont dans `Settings.allowed_hosts` (`keyserver.internal` par défaut, `KEYSERVER_ALLOWED_HOSTS` pour un essai local).
- Tâche 4: `httpx2` remplace `httpx` (Starlette déconseille `httpx` pour son `TestClient`). Dépendances scindées: `requirements.txt` et `requirements.lock` pour l'exécution, `requirements-dev.txt` et `requirements-dev.lock` pour les tests (venv de dev et CI).
- Tâche 8: le masque du champ clé est `*` (le test de style interdit la puce).
- Tâche 9: liste avec boutons par ligne au lieu d'un tableau à sélection; la clé générée reste visible jusqu'à *Masquer* (elle se recalcule, elle n'est donc plus "affichée une seule fois"); le menu suit les pages construites (Administration en dernier).
- Le test d'intégration d'un flux trop gros sur une vraie route existe (`POST /admin/revoke`).


**Hors périmètre, inchangé**
- Route d'ingestion, envoi automatique des relevés, médiane entre contributeurs, journal d'audit, rotation du secret, plusieurs administrateurs.
