# Capture des prix HDV v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturer passivement le trafic TCP 5555 de Dofus 3, décoder les prix de lots et les cours du marché de l'HDV, les stocker dans SQLite et les exposer en ligne de commande (liste, historique, export CSV).

**Architecture:** Pipeline en couches à sens unique: capture Scapy, reconstruction TCP, extraction des enveloppes de messages, décodeur Protobuf générique, décodeurs HDV, file d'attente vers un thread d'écriture SQLite. La logique pure (tcp, protobuf, framing, hdv, market_stats) ne dépend ni de Scapy ni de SQLite. Les noms de messages et numéros de champs sont isolés dans un seul module de configuration.

**Tech Stack:** Python 3.13, Scapy, SQLite (stdlib `sqlite3`), pytest, Npcap 1.90, PowerShell (`dev.ps1`).

**Spec:** `docs/superpowers/specs/2026-11-09-hdv-price-capture-v1-design.md`

## Global Constraints

- Windows 11, Python 3.13, venv `.venv`, dépendances dans `requirements.txt` (`scapy>=2.6,<3`, `pytest>=8,<9`).
- Fonctions de 20 lignes maximum, modules de 200 lignes maximum, noms explicites en anglais (`snake_case`, `PascalCase`, `UPPER_CASE`), annotations de type partout, pas d'`except:` nu, logs via `logging`.
- Capture strictement passive: filtre `tcp port 5555`, aucun envoi réseau sortant, aucun paquet brut écrit sur disque.
- Lots ×1, ×10, ×100, ×1000 avec le prix total du lot (jamais le prix unitaire).
- Historique complet des relevés conservé (pas seulement le dernier prix).
- Les écritures SQLite se font hors de la boucle de capture.
- Noms de messages et numéros de champs uniquement dans `src/opendofusdata/messages.py`.
- Le code vit dans `src/opendofusdata/`, les tests dans `tests/`.

## Review Focus

- Un paquet perdu en cours de flux: le flux se resynchronise et les messages suivants sont décodés (test dans Task 2).
- Outil lancé en cours de connexion: l'extracteur retrouve les enveloppes sans début de flux (test dans Task 4).
- Padding Ethernet sur un ACK vide: aucun octet de remplissage n'entre dans le flux (test dans Task 2).
- Message tronqué ou octets invalides: le décodeur lève une `DecodeError` sans faire tomber la capture (tests dans Tasks 3 et 8).
- Un message HDV dont les champs sont absents ou de type inattendu: ignoré et journalisé, jamais de prix inventé (test dans Task 8).

---

### Task 1: Squelette du projet

**Files:**
- Create: `src/opendofusdata/__init__.py`, `tests/__init__.py`, `pytest.ini`, `.gitignore`
- Modify: `dev.ps1` (aucune modification attendue si `pytest.ini` fixe `pythonpath = src`)

**Interfaces:**
- Produces: package importable `opendofusdata`; `pytest` trouve `src/` via `pytest.ini`.

- [ ] **Step 1:** `git init` à la racine; `.gitignore` contient `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.db`, `captures/`.
- [ ] **Step 2:** `pytest.ini` avec `[pytest]`, `pythonpath = src`, `testpaths = tests`.
- [ ] **Step 3:** Test `tests/test_package.py::test_package_is_importable` (`import opendofusdata`).
- [ ] **Step 4:** `.\dev.ps1 setup` puis `.\dev.ps1 test`. Expected: 1 passed.
- [ ] **Step 5:** Commit `chore: project skeleton`.

### Task 2: Reconstruction TCP

**Files:**
- Create: `src/opendofusdata/tcp.py`
- Test: `tests/test_tcp.py`

**Interfaces:**
- Produces:
  - `payload_length(ip_total_length: int, ip_header_length: int, tcp_header_length: int) -> int` (longueur des données TCP d'après l'en-tête IP, jamais d'après la taille de la trame Ethernet).
  - `FlowKey = tuple[str, int, str, int]` (src_ip, src_port, dst_ip, dst_port).
  - `@dataclass Reassembled: data: bytes; resynced: bool`.
  - `class StreamReassembler: __init__(self, max_buffered_bytes: int = 65536)`; `feed(self, seq: int, payload: bytes) -> Reassembled`.
  - `class FlowTable: __init__(self, idle_seconds: float = 300.0)`; `feed(self, key: FlowKey, seq: int, payload: bytes, now: float) -> Reassembled`; `purge(self, now: float) -> int` (retourne le nombre de flux supprimés).

- [ ] **Step 1: Tests (`tests/test_tcp.py`)**, noms et assertions:
  - `test_payload_length_ignores_ethernet_padding`: `payload_length(40, 20, 20) == 0`.
  - `test_in_order_segments_are_concatenated`: segments `seq=100 b"ab"`, `seq=102 b"cd"` donnent `b"ab"` puis `b"cd"`.
  - `test_out_of_order_segment_is_held_until_gap_filled`: `seq=102 b"cd"` seul donne `b""`; puis `seq=100 b"ab"` donne `b"abcd"`.
  - `test_retransmitted_segment_is_ignored`: un segment déjà livré renvoie `b""`.
  - `test_sequence_wraparound`: départ à `seq=2**32 - 2` avec `b"abcd"` puis `seq=2` avec `b"ef"` donne `b"ef"`.
  - `test_lost_packet_triggers_resync`: un trou jamais comblé avec plus de `max_buffered_bytes` en attente donne `resynced=True` et les octets suivants sont livrés.
  - `test_mid_connection_start_uses_first_segment_as_base`.
  - `test_flow_table_purges_idle_flows`: un flux inactif depuis plus de `idle_seconds` est supprimé par `purge`.
- [ ] **Step 2:** Lancer `pytest tests/test_tcp.py -v`. Expected: FAIL (module absent).
- [ ] **Step 3:** Implémenter `tcp.py`. Numéros de séquence ramenés à un décalage 64 bits relatif au premier segment (gère le passage de 2³²); segments hors ordre gardés dans un dictionnaire par décalage; au dépassement de `max_buffered_bytes`, abandonner le trou, livrer les données suivantes avec `resynced=True`.
- [ ] **Step 4:** Lancer les tests. Expected: PASS.
- [ ] **Step 5:** Commit `feat: tcp stream reassembly with resync`.

### Task 3: Décodeur Protobuf générique

**Files:**
- Create: `src/opendofusdata/protobuf.py`
- Test: `tests/test_protobuf.py`

**Interfaces:**
- Produces:
  - `class DecodeError(ValueError)`.
  - `Field = tuple[int, int, int | bytes]` (numéro de champ, wire type, valeur: entier pour varint/fixed, `bytes` pour length-delimited).
  - `read_varint(data: bytes, offset: int) -> tuple[int, int]` (valeur, nouvel offset).
  - `decode_fields(data: bytes) -> list[Field]`.
  - `try_decode_fields(data: bytes) -> list[Field] | None` (retourne `None` au lieu de lever, pour l'inspection de sous-messages).
  - `to_signed(value: int) -> int` (complément à deux 64 bits) et `zigzag_decode(value: int) -> int`.

- [ ] **Step 1: Tests**:
  - `test_read_varint_multibyte`: `read_varint(b"\xac\x02", 0) == (300, 2)`.
  - `test_decode_fields_mixed_types`: `decode_fields(bytes.fromhex("08960112024869"))` donne `[(1, 0, 150), (2, 2, b"Hi")]`.
  - `test_truncated_varint_raises_decode_error`; `test_truncated_length_delimited_raises_decode_error`; `test_unknown_wire_type_raises_decode_error`.
  - `test_try_decode_fields_returns_none_on_garbage`.
  - `test_zigzag_decode`: `zigzag_decode(1) == -1`, `zigzag_decode(2) == 1`.
- [ ] **Step 2:** Run `pytest tests/test_protobuf.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implémenter (wire types 0, 1, 2, 5; types 3 et 4 rejetés).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat: generic protobuf decoder`.

### Task 4: Extraction des enveloppes de messages

**Files:**
- Create: `src/opendofusdata/framing.py`
- Test: `tests/test_framing.py`

**Interfaces:**
- Consumes: `decode_fields`, `try_decode_fields`, `read_varint` de `protobuf.py`.
- Produces:
  - `TYPE_URL_PREFIX = b"type.ankama.com/"`.
  - `@dataclass Envelope: type_name: str; payload: bytes`.
  - `class EnvelopeExtractor: __init__(self)`; `feed(self, data: bytes) -> list[Envelope]`; `reset(self) -> None` (à appeler sur `resynced=True`).

Hypothèse à confirmer avec une vraie capture (Task 7): une enveloppe est un message Protobuf contenant l'URL de type `type.ankama.com/<nom>` et un champ `bytes` portant la charge utile. L'extracteur ne suppose aucun début de flux: il cherche la chaîne `TYPE_URL_PREFIX` dans le tampon, remonte au début du message length-delimited qui la contient, tente `try_decode_fields`, et garde en tampon (borné) les octets incomplets.

- [ ] **Step 1: Tests** (sur des enveloppes construites à la main dans le test):
  - `test_single_envelope_extracted`.
  - `test_envelope_split_across_two_feeds`: la même enveloppe coupée au milieu est livrée au second `feed`.
  - `test_stream_started_mid_message_skips_garbage`: des octets aléatoires avant la première enveloppe sont ignorés.
  - `test_two_envelopes_in_one_feed`.
  - `test_reset_drops_partial_buffer`.
  - `test_buffer_is_bounded`: après 1 Mo de données sans enveloppe, le tampon interne ne dépasse pas sa borne.
- [ ] **Step 2:** Run `pytest tests/test_framing.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implémenter `framing.py` avec une constante `MAX_BUFFER_BYTES = 262144`.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat: envelope extraction from tcp stream`.

### Task 5: Stockage SQLite

**Files:**
- Create: `src/opendofusdata/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Produces:
  - `LOT_SIZES = (1, 10, 100, 1000)`.
  - `@dataclass LotPrice: item_id: int; server: str; lot_size: int; price: int; captured_at: str` (ISO 8601 UTC).
  - `@dataclass MarketStats: item_id: int; server: str; period: str` (`"24h"`, `"7d"`, `"30d"`), `points: list[tuple[int, int]]` (horodatage Unix, prix), `median: int`, `mean: int`, `sold_count: int`, `server_updated_at: str`, `last_purchase_at: str`, `captured_at: str`.
  - `class PriceStore: __init__(self, path: str)`; `save_lot_price(self, lot: LotPrice) -> None`; `save_market_stats(self, stats: MarketStats) -> None`; `latest_prices(self, item_id: int | None = None) -> list[LotPrice]`; `price_history(self, item_id: int, lot_size: int) -> list[LotPrice]`; `iter_lot_prices(self) -> Iterator[LotPrice]` (pour l'export CSV); `close(self) -> None`.
  - `class StoreWriter: __init__(self, store_path: str)`; `submit(self, record: LotPrice | MarketStats) -> None` (non bloquant, file d'attente); `stop(self) -> None` (vide la file puis joint le thread). Le thread ouvre sa propre connexion SQLite.

- [ ] **Step 1: Tests**: `test_history_keeps_every_capture` (deux relevés du même objet gardent les deux lignes), `test_latest_prices_returns_most_recent_per_lot_size`, `test_lot_size_outside_lot_sizes_is_rejected` (`ValueError`), `test_market_stats_roundtrip_keeps_points_and_dates`, `test_store_writer_persists_records_from_another_thread`.
- [ ] **Step 2:** Run `pytest tests/test_storage.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implémenter; les `points` sont sérialisés en JSON dans une colonne texte; schéma créé à l'ouverture (`CREATE TABLE IF NOT EXISTS`).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat: sqlite price store with threaded writer`.

### Task 6: Capture Scapy et mode découverte

**Files:**
- Create: `src/opendofusdata/capture.py`, `src/opendofusdata/discovery.py`, `src/opendofusdata/cli.py`
- Test: `tests/test_discovery.py`

**Interfaces:**
- Consumes: `FlowTable`, `payload_length` (Task 2); `EnvelopeExtractor`, `Envelope` (Task 4); `try_decode_fields`, `Field` (Task 3).
- Produces:
  - `DOFUS_PORT = 5555`, `BPF_FILTER = "tcp port 5555"` dans `capture.py`.
  - `class PacketPipeline: __init__(self, on_envelope: Callable[[Envelope], None])`; `handle_packet(self, packet) -> None` (extrait la charge utile via `payload_length`, un `EnvelopeExtractor` par flux, `reset()` sur `resynced`).
  - `run_capture(pipeline: PacketPipeline, interface: str | None = None) -> None` (boucle `scapy.sniff(filter=BPF_FILTER, store=False, prn=pipeline.handle_packet)`).
  - `describe_envelope(envelope: Envelope) -> dict` dans `discovery.py`: `{"type": nom, "size": octets, "fields": [{"number", "wire_type", "preview"}]}`, avec décodage récursif des sous-messages et aperçu des valeurs (pas de paquets bruts écrits).
  - `class DiscoveryLogger: __init__(self, path: str)`; `log(self, envelope: Envelope) -> None` (une ligne JSON par enveloppe, ajoutée à `captures/discovery.jsonl`).
  - `cli.py`: `main(argv: list[str] | None = None) -> int` avec la sous-commande `discover [--interface NOM] [--output CHEMIN]`.

- [ ] **Step 1: Tests**: `test_describe_envelope_lists_top_level_fields`, `test_describe_envelope_decodes_nested_message`, `test_describe_envelope_survives_undecodable_payload` (renvoie les octets en hexadécimal tronqué, sans lever), `test_discovery_logger_appends_one_json_line_per_envelope`, `test_cli_discover_parses_arguments` (sans lancer de capture, en injectant une fonction de capture factice).
- [ ] **Step 2:** Run `pytest tests/test_discovery.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implémenter les trois modules; `handle_packet` reste testable avec un faux paquet (objet simple exposant IP et TCP) sans Npcap.
- [ ] **Step 4:** Run `.\dev.ps1 test`. Expected: tout PASS.
- [ ] **Step 5:** Commit `feat: scapy capture and discovery mode`.

### Task 7: Capture réelle et rétro-ingénierie (terminé avec le joueur)

Les deux captures du joueur (objets Ailes de Moskito, Aile du Tofu Maléfique, Âme capturée: Fourapin le Chaud) ont été croisées avec l'écran. Les conclusions sont dans `docs/protocol-notes.md`, qui fait foi pour les tâches 8 à 10. Résumé:

- Format confirmé: messages Protobuf précédés de leur longueur, enveloppes `type.ankama.com/<nom>`.
- Lots: réponse serveur `jzs`; champ 1 = `{1: identifiant d'objet, 2: prix des lots en entiers variables compactés (un par taille de LOT_SIZES, 0 = pas de lot de cette taille), 3: ?, 4: ?}`, champ 2 = ?, champ 3 = identifiant d'objet. Valeurs vérifiées: 307 → `ee05ec2dc986039fc21e` = [750, 5868, 49993, 499999]; 376 → `9101d00ebd6500` = [145, 1872, 12989, 0]; 34095 → `a98805000000` = [82985, 0, 0, 0]; 1022 → `01f306c42c00` = [1, 883, 5700, 0].
- Cours du marché: réponse serveur `ire` à la requête `iqp` (champ 1 = identifiant d'objet). Champ 1 répété = points des 24 heures, champ 3 répété = points des 30 jours. Chaque point = `{1: prix, 2: identifiant d'objet, 3: horodatage ISO-8601 UTC en texte (ex. 2026-11-09T10:50:09.901212706Z), 4: quantité vendue}`.
- Dérivés vérifiés sur l'écran pour les trois objets: médian et moyenne pondérés par les quantités (moyenne tronquée à l'entier), articles vendus = somme des quantités, « dernier achat » = horodatage du dernier point des 24 heures, l'onglet 7 jours = points des 30 jours situés au plus 7 jours avant le dernier point (aucun message dédié).
- « Dernière mise à jour »: aucun champ serveur trouvé; elle vaut l'heure de la requête. On utilise l'heure de capture.
- Les messages ne contiennent pas les noms d'objets, seulement les identifiants.

### Task 8: Décodage des lots HDV

**Files:**
- Create: `src/opendofusdata/messages.py`, `src/opendofusdata/hdv.py`
- Test: `tests/test_hdv.py`

**Interfaces:**
- Consumes: `Envelope` (framing), `decode_fields`, `try_decode_fields`, `read_varint`, `DecodeError` (protobuf), `LotPrice`, `LOT_SIZES` (storage).
- Produces:
  - `messages.py`: uniquement des constantes nommées, seul endroit où figurent les noms de messages et numéros de champs: `LOT_RESPONSE_TYPE = "jzs"`, `LOT_DETAIL_FIELD = 1`, `LOT_ITEM_FIELD = 1`, `LOT_PRICES_FIELD = 2`, `LOT_FALLBACK_ITEM_FIELD = 3`, `STATS_RESPONSE_TYPE = "ire"`, `STATS_HOURLY_POINTS_FIELD = 1`, `STATS_DAILY_POINTS_FIELD = 3`, `POINT_PRICE_FIELD = 1`, `POINT_ITEM_FIELD = 2`, `POINT_TIMESTAMP_FIELD = 3`, `POINT_QUANTITY_FIELD = 4`.
  - `hdv.py`: `decode_lot_prices(envelope: Envelope, server: str, captured_at: str) -> list[LotPrice]`, qui renvoie une liste vide pour un message d'un autre type ou invalide (avec un log `WARNING` pour un `jzs` illisible) et `unpack_varints(data: bytes) -> list[int]` (entiers compactés; lève `DecodeError` si les octets ne forment pas une suite complète d'entiers variables).

- [ ] **Step 1: Tests (`tests/test_hdv.py`)**, avec des enveloppes construites dans le test à partir des octets réels:
  - `test_decodes_four_lot_prices_for_item_307`: les octets `ee05ec2dc986039fc21e` donnent des `LotPrice` (objet 307) pour les tailles 1, 10, 100, 1000 avec les prix totaux 750, 5868, 49993, 499999.
  - `test_zero_price_means_no_lot_of_that_size`: `9101d00ebd6500` (objet 376) donne seulement les tailles 1, 10, 100 (145, 1872, 12989).
  - `test_single_lot_item`: `a98805000000` (objet 34095) donne seulement la taille 1 au prix 82985.
  - `test_item_id_falls_back_to_outer_field`: sans le champ 1.1, l'identifiant vient du champ 3 du message.
  - `test_unrelated_envelope_returns_empty_list`.
  - `test_more_than_four_prices_is_rejected_and_logged` (avec `caplog`): cinq valeurs donnent une liste vide.
  - `test_truncated_packed_prices_are_skipped_without_raising`: octets `ee05ec` (entier variable coupé) donnent une liste vide et un `WARNING`.
  - `test_missing_prices_field_returns_empty_list`.
  - `test_unpack_varints_roundtrip` et `test_unpack_varints_rejects_truncated_input`.
- [ ] **Step 2:** Run `.venv/Scripts/python.exe -m pytest tests/test_hdv.py -v -W error`. Expected: FAIL.
- [ ] **Step 3:** Implémenter `messages.py` et `hdv.py` (fonctions courtes: sélection du message, lecture des prix compactés, association aux tailles de `LOT_SIZES`).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat: decode hdv lot prices`.

### Task 9: Décodage des cours du marché

**Files:**
- Create: `src/opendofusdata/timeutil.py`, `src/opendofusdata/market_stats.py`
- Modify: `src/opendofusdata/storage.py` (annotation seulement: `MarketStats.points` devient `list[tuple[int, int, int]]` = horodatage Unix, prix, quantité; ne pas dépasser 200 lignes), `tests/test_storage.py` (fixtures à trois valeurs)
- Test: `tests/test_market_stats.py`, `tests/test_timeutil.py`

**Interfaces:**
- Consumes: `Envelope`, `decode_fields`, `DecodeError`, constantes de `messages.py`, `MarketStats`, `MARKET_PERIODS` (storage).
- Produces:
  - `timeutil.py`: `format_utc(moment: datetime) -> str` (format unique `%Y-%m-%dT%H:%M:%SZ`, toujours en UTC, utilisé pour tous les horodatages stockés) et `parse_server_timestamp(text: str) -> datetime` (accepte `2026-11-09T10:50:09.901212706Z`, c'est-à-dire jusqu'à 9 chiffres de fraction, renvoie un `datetime` UTC; `ValueError` sinon).
  - `market_stats.py`: `decode_market_stats(envelope: Envelope, server: str, captured_at: str) -> list[MarketStats]`, une entrée par période non vide parmi `"24h"` (champ 1), `"30d"` (champ 3) et `"7d"` (points des 30 jours situés au plus 7 jours avant le dernier point des 30 jours); liste vide pour un autre type de message ou un message illisible (avec `WARNING`).
- Règles de calcul (vérifiées sur l'écran): `sold_count` = somme des quantités; `median` = médiane de l'ensemble où chaque prix est répété autant de fois que sa quantité (moyenne entière des deux valeurs centrales si le total est pair), sans développer la liste; `mean` = somme(prix × quantité) // somme(quantités) (tronqué); `server_updated_at` = `captured_at`; `last_purchase_at` = horodatage du dernier point de la période 24 h (à défaut, du dernier point des 30 jours), formaté avec `format_utc`; `points` triés par horodatage.

- [ ] **Step 1: Tests**:
  - `test_timeutil.py`: `parse_server_timestamp("2026-11-09T10:50:09.901212706Z")` donne le 2026-11-09 10:50:09 UTC (microsecondes 901212); un texte invalide lève `ValueError`; `format_utc` donne `2026-11-09T10:50:09Z`.
  - `test_market_stats.py` (enveloppes `ire` construites à la main):
    - `test_two_single_sale_points_give_mean_and_median_of_both` (valeurs de l'Âme capturée: deux points 91998 et 25000, quantité 1 chacun → médian 58499, moyen 58499, vendus 2).
    - `test_median_and_mean_are_weighted_by_quantity` (cas à trois points calculé à la main).
    - `test_mean_is_truncated_not_rounded` (moyenne 568,7 → 568).
    - `test_seven_day_period_uses_points_within_seven_days_of_last_point` (points des 30 jours aux jours J-9, J-7 (exactement 7 jours: inclus), J-3, J).
    - `test_last_purchase_is_last_hourly_point_timestamp` et `test_last_purchase_falls_back_to_last_daily_point_when_no_hourly_points`.
    - `test_period_without_points_is_omitted`.
    - `test_points_are_sorted_by_timestamp`.
    - `test_unrelated_envelope_returns_empty_list`; `test_missing_item_or_timestamp_is_skipped_and_logged`; `test_truncated_payload_is_skipped_without_raising`.
- [ ] **Step 2:** Run `.venv/Scripts/python.exe -m pytest tests/test_timeutil.py tests/test_market_stats.py -v -W error`. Expected: FAIL.
- [ ] **Step 3:** Implémenter (fonctions courtes: lecture d'un point, regroupement par période, statistiques, sélection de la fenêtre de 7 jours).
- [ ] **Step 4:** Run, puis la suite complète. Expected: PASS.
- [ ] **Step 5:** Commit `feat: decode market stats`.

### Task 10: Commandes CLI et assemblage

**Files:**
- Modify: `src/opendofusdata/cli.py` (déjà proche de la limite: si la limite de 200 lignes est menacée, créer `src/opendofusdata/commands.py` pour les commandes de lecture et le dire dans le rapport)
- Create: `src/opendofusdata/export.py`, `src/opendofusdata/run_pipeline.py`
- Test: `tests/test_cli.py`, `tests/test_export.py`, `tests/test_run_pipeline.py`

**Interfaces:**
- Consumes: `PacketPipeline`, `CaptureAborted`, `run_capture` (capture); `decode_lot_prices` (hdv); `decode_market_stats` (market_stats); `StoreWriter`, `PriceStore`, `LotPrice`, `MarketStats` (storage); `format_utc` (timeutil).
- Produces:
  - `export.py`: `write_lot_prices_csv(prices: Iterable[LotPrice], output: TextIO) -> None` (colonnes `item_id,server,lot_size,price,captured_at`).
  - `run_pipeline.py`: `make_envelope_handler(writer: StoreWriter, server: str, now: Callable[[], datetime]) -> Callable[[Envelope, FlowKey], None]` qui décode lots et cours, formate l'heure de capture avec `format_utc` (UTC, format unique) et soumet chaque enregistrement à `writer.submit`, sans écrire en base dans la boucle de capture.
  - Sous-commandes de `cli.main` (en plus de `discover`): `run [--db CHEMIN] [--interface NOM] [--server NOM]` (défaut `--db prices.db`, `--server unknown`; arrêt propre sur Ctrl+C avec `writer.stop()`; mêmes messages d'erreur en français que `discover`), `prices [--db] [--item ID]`, `history ITEM_ID --lot TAILLE [--db]`, `stats ITEM_ID [--period 24h|7d|30d] [--db]`, `export-csv --output CHEMIN [--db]`. Les objets sont désignés par leur identifiant (les noms ne figurent pas dans le trafic).

- [ ] **Step 1: Tests**: `test_export_writes_header_and_rows`; `test_handler_stores_lot_prices_and_market_stats` (enveloppes `jzs` et `ire` synthétiques, `now` injecté, base temporaire lue après `writer.stop()`; les horodatages stockés sont en UTC au format `YYYY-MM-DDTHH:MM:SSZ`); `test_handler_ignores_unrelated_envelopes`; `test_cli_prices_lists_latest_prices`; `test_cli_history_filters_by_item_and_lot`; `test_cli_stats_prints_requested_period`; `test_cli_export_csv_creates_file`; `test_cli_run_stops_cleanly_on_keyboard_interrupt` (capture injectée qui lève `KeyboardInterrupt`; la file est vidée avant la sortie); `test_cli_run_reports_unwritable_database` (chemin dont le dossier parent n'existe pas: message en français, code non nul).
- [ ] **Step 2:** Run `.venv/Scripts/python.exe -m pytest tests/test_cli.py tests/test_export.py tests/test_run_pipeline.py -v -W error`. Expected: FAIL.
- [ ] **Step 3:** Implémenter.
- [ ] **Step 4:** Run `.\dev.ps1 test`. Expected: tout PASS.
- [ ] **Step 5:** Commit `feat: cli commands and csv export`.

### Task 11: Validation avec le jeu et documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** Le joueur lance `python -m opendofusdata run`, consulte plusieurs objets à l'HDV, puis `python -m opendofusdata prices` et compare avec les prix affichés en jeu (lots et, si disponibles, cours du marché).
- [ ] **Step 2:** Corriger `messages.py` ou les décodeurs d'après les écarts.
- [ ] **Step 3:** Mettre à jour `README.md`: usage des commandes `discover`, `run`, `prices`, `history`, `export-csv`, avertissement sur les mises à jour de Dofus (noms de messages à ajuster) et retrait de la mention « code de capture non écrit ».
- [ ] **Step 4:** Commit `docs: usage and v1 validation`.
