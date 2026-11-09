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
- Noms de messages et numéros de champs uniquement dans `src/dofus_prices/messages.py`.
- Le code vit dans `src/dofus_prices/`, les tests dans `tests/`.

## Review Focus

- Un paquet perdu en cours de flux: le flux se resynchronise et les messages suivants sont décodés (test dans Task 2).
- Outil lancé en cours de connexion: l'extracteur retrouve les enveloppes sans début de flux (test dans Task 4).
- Padding Ethernet sur un ACK vide: aucun octet de remplissage n'entre dans le flux (test dans Task 2).
- Message tronqué ou octets invalides: le décodeur lève une `DecodeError` sans faire tomber la capture (tests dans Tasks 3 et 8).
- Un message HDV dont les champs sont absents ou de type inattendu: ignoré et journalisé, jamais de prix inventé (test dans Task 8).

---

### Task 1: Squelette du projet

**Files:**
- Create: `src/dofus_prices/__init__.py`, `tests/__init__.py`, `pytest.ini`, `.gitignore`
- Modify: `dev.ps1` (aucune modification attendue si `pytest.ini` fixe `pythonpath = src`)

**Interfaces:**
- Produces: package importable `dofus_prices`; `pytest` trouve `src/` via `pytest.ini`.

- [ ] **Step 1:** `git init` à la racine; `.gitignore` contient `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.db`, `captures/`.
- [ ] **Step 2:** `pytest.ini` avec `[pytest]`, `pythonpath = src`, `testpaths = tests`.
- [ ] **Step 3:** Test `tests/test_package.py::test_package_is_importable` (`import dofus_prices`).
- [ ] **Step 4:** `.\dev.ps1 setup` puis `.\dev.ps1 test`. Expected: 1 passed.
- [ ] **Step 5:** Commit `chore: project skeleton`.

### Task 2: Reconstruction TCP

**Files:**
- Create: `src/dofus_prices/tcp.py`
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
- Create: `src/dofus_prices/protobuf.py`
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
- Create: `src/dofus_prices/framing.py`
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
- Create: `src/dofus_prices/storage.py`
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
- Create: `src/dofus_prices/capture.py`, `src/dofus_prices/discovery.py`, `src/dofus_prices/cli.py`
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

### Task 7: Point de contrôle, capture réelle et rétro-ingénierie (avec le joueur)

**Files:**
- Create: `src/dofus_prices/messages.py`, `docs/protocol-notes.md`

**Interfaces:**
- Produces dans `messages.py`: pour chaque message utile (consultation de lots, statistiques de marché), une constante de nom de message et un `@dataclass(frozen=True)` listant les numéros de champs (prix de lot, taille de lot, identifiant d'objet, séries de points, médian, moyen, articles vendus, dates). Valeurs de départ tirées d'Astrub Companion pour les lots; les statistiques de marché sont à découvrir.

- [ ] **Step 1:** Le joueur lance `python -m dofus_prices discover` en administrateur si Npcap l'exige, avant de lancer Dofus, puis consulte à l'HDV deux ou trois objets (lots ×1, ×10, ×100, ×1000) et ouvre l'écran de statistiques sur 24 h, 7 jours et 30 jours.
- [ ] **Step 2:** Le joueur envoie `captures/discovery.jsonl`.
- [ ] **Step 3:** Identifier les messages de consultation et de statistiques en comparant les valeurs affichées en jeu (médian, moyen, articles vendus, dernière mise à jour, dernier achat) aux champs du log; noter les conclusions dans `docs/protocol-notes.md`.
- [ ] **Step 4:** Remplir `messages.py`. Si les statistiques de marché sont absentes du trafic, le noter dans `docs/protocol-notes.md` et retirer Task 9 de la v1 (voir spec, « Point incertain »).
- [ ] **Step 5:** Commit `docs: protocol notes and message definitions`.

### Task 8: Décodage des lots HDV

**Files:**
- Create: `src/dofus_prices/hdv.py`
- Test: `tests/test_hdv.py`

**Interfaces:**
- Consumes: `Envelope`, `decode_fields`, `DecodeError`, définitions de `messages.py` (Task 7), `LotPrice` (Task 5).
- Produces: `decode_lot_prices(envelope: Envelope, server: str, captured_at: str) -> list[LotPrice]` (liste vide pour un message non reconnu ou incomplet; une ligne de log `WARNING` explique pourquoi).

- [ ] **Step 1: Tests**, construits à partir des champs observés au Task 7 (messages synthétiques, plus un extrait réel anonymisé du log):
  - `test_decodes_one_price_per_lot_size`: les quatre tailles (1, 10, 100, 1000) ressortent avec le prix total du lot.
  - `test_price_is_total_lot_price_not_unit_price`.
  - `test_unrelated_envelope_returns_empty_list`.
  - `test_missing_price_field_is_skipped_and_logged` (avec `caplog`).
  - `test_truncated_payload_is_skipped_without_raising`.
  - `test_lot_size_outside_known_sizes_is_ignored`.
- [ ] **Step 2:** Run `pytest tests/test_hdv.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implémenter `decode_lot_prices`, découpé en petites fonctions (sélection du message, lecture d'un lot, validation).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat: decode hdv lot prices`.

### Task 9: Décodage des cours du marché (si présents dans le trafic)

**Files:**
- Create: `src/dofus_prices/market_stats.py`
- Test: `tests/test_market_stats.py`

**Interfaces:**
- Consumes: `Envelope`, définitions de `messages.py`, `MarketStats` (Task 5).
- Produces: `decode_market_stats(envelope: Envelope, server: str, captured_at: str) -> list[MarketStats]` (une entrée par période présente dans le message).

- [ ] **Step 1: Tests**: `test_decodes_median_mean_and_sold_count` (valeurs de l'écran de référence: médian 7 466, moyen 10 028, 66 articles vendus pour la période 24 h), `test_decodes_curve_points_in_order`, `test_server_update_and_last_purchase_dates_are_kept`, `test_each_period_is_returned_separately`, `test_unrelated_envelope_returns_empty_list`, `test_missing_fields_are_skipped_and_logged`.
- [ ] **Step 2:** Run `pytest tests/test_market_stats.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implémenter sur le modèle de `hdv.py`.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat: decode market stats`.

### Task 10: Commandes CLI et assemblage

**Files:**
- Modify: `src/dofus_prices/cli.py`
- Create: `src/dofus_prices/__main__.py`, `src/dofus_prices/export.py`
- Test: `tests/test_cli.py`, `tests/test_export.py`

**Interfaces:**
- Consumes: `PacketPipeline`, `run_capture` (Task 6); `decode_lot_prices` (Task 8); `decode_market_stats` (Task 9); `StoreWriter`, `PriceStore` (Task 5).
- Produces:
  - `export.py`: `write_lot_prices_csv(prices: Iterable[LotPrice], output: TextIO) -> None` (colonnes `item_id,server,lot_size,price,captured_at`).
  - Sous-commandes de `cli.main`: `run [--db CHEMIN] [--interface NOM] [--server NOM]` (capture, décodage, écriture via `StoreWriter`), `prices [--item ID]`, `history ITEM_ID --lot TAILLE`, `export-csv --output CHEMIN`.
  - `python -m dofus_prices` appelle `main`.

- [ ] **Step 1: Tests**: `test_export_writes_header_and_rows`, `test_cli_prices_lists_latest_prices` (base temporaire), `test_cli_history_filters_by_item_and_lot`, `test_cli_export_csv_creates_file`, `test_run_pipeline_stores_decoded_prices` (enveloppe synthétique injectée dans le callback, vérifie la ligne en base).
- [ ] **Step 2:** Run `pytest tests/test_cli.py tests/test_export.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implémenter; le callback de `run` décode l'enveloppe et appelle `StoreWriter.submit`, sans écrire en base dans la boucle de capture; arrêt propre sur Ctrl+C (`stop()` vide la file).
- [ ] **Step 4:** Run `.\dev.ps1 test`. Expected: tout PASS.
- [ ] **Step 5:** Commit `feat: cli commands and csv export`.

### Task 11: Validation avec le jeu et documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** Le joueur lance `python -m dofus_prices run`, consulte plusieurs objets à l'HDV, puis `python -m dofus_prices prices` et compare avec les prix affichés en jeu (lots et, si disponibles, cours du marché).
- [ ] **Step 2:** Corriger `messages.py` ou les décodeurs d'après les écarts.
- [ ] **Step 3:** Mettre à jour `README.md`: usage des commandes `discover`, `run`, `prices`, `history`, `export-csv`, avertissement sur les mises à jour de Dofus (noms de messages à ajuster) et retrait de la mention « code de capture non écrit ».
- [ ] **Step 4:** Commit `docs: usage and v1 validation`.
