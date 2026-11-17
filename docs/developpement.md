# Documentation développeur

Ce document regroupe tout ce qui concerne le développement et l'usage en ligne de commande d'OpenDofusData. Pour installer et utiliser l'outil, voir le [README](../README.md).

## Prérequis

- Windows 11
- Python 3.13
- [Npcap](https://npcap.com) (voir le README)
- Dofus 3 lancé sur la même machine que l'outil.

## Installation

Depuis PowerShell, à la racine du projet:

```powershell
.\dev.ps1 setup
```

Cette commande crée le venv `.venv` et installe `requirements.txt` (`scapy` pour la capture, `customtkinter` pour la fenêtre, `pytest` pour les tests, `pyinstaller` pour l'exécutable; le décodage Protobuf et SQLite utilisent la bibliothèque standard). Si PowerShell refuse d'exécuter le script, lance une fois `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Npcap étant installé au niveau du système, il fonctionne depuis le venv sans configuration.

Le projet est aussi un paquet Python (`pyproject.toml`). Dans le venv, `pip install -e .` installe la commande `opendofusdata`, équivalente à `python -m opendofusdata` (ex. `opendofusdata window`, `opendofusdata run --server Kourial`). `.\dev.ps1 setup` fait cette installation. Au premier lancement de `window` ou `run` dans un terminal, la liste des serveurs de jeu est proposée (le choix est mémorisé, voir « Serveur de jeu »); `--server NOM` et `--choose-server` fonctionnent aussi.

### Dépendances verrouillées

`requirements.txt` est le fichier écrit à la main (fourchettes de versions). `requirements.lock` en est la version verrouillée: chaque paquet, y compris les dépendances indirectes, y figure avec sa version exacte et ses empreintes SHA-256. `.\dev.ps1 setup` et les workflows GitHub l'installent avec `pip install --require-hashes`, donc l'exécutable publié ne dépend pas de ce que pip trouverait le jour du build. Pour changer une dépendance, modifie `requirements.txt` puis régénère le verrou (Python 3.13, sous Windows):

```powershell
python -m pip install pip-tools
python -m piptools compile --generate-hashes --allow-unsafe --strip-extras -o requirements.lock requirements.txt
```

Les actions GitHub des workflows sont épinglées par empreinte de commit (le tag est rappelé en commentaire). Pour les mettre à jour, résous le nouveau tag avec `git ls-remote --tags https://github.com/actions/<nom>` et remplace l'empreinte.

### Construire l'exécutable et publier une version

`.\dev.ps1 build` produit `dist\OpenDofusData.exe` (PyInstaller, sans console) et `dist\OpenDofusData.exe.sha256`. Pour publier: change `__version__`, commite sur `main`, puis crée et pousse le tag `vX.Y.Z`. Le workflow GitHub `.github/workflows/release.yml` lance les tests, vérifie que le tag correspond à la version, construit l'exécutable et le publie sur la Release avec son empreinte: c'est ce que la page À propos des programmes installés va chercher. Le workflow `ci.yml` lance les tests à chaque push sur `main` et chaque pull request.

## Script de dev

| Commande | Effet |
|---|---|
| `.\dev.ps1 setup` | Crée le venv et installe les dépendances |
| `.\dev.ps1 test` | Lance `pytest` dans le venv |
| `.\dev.ps1 clean` | Supprime le venv, les caches, `build\` et `dist\` |
| `.\dev.ps1 build` | Construit `dist\OpenDofusData.exe` et sa somme SHA-256 |
| `.\dev.ps1 capture [options]` | Lance la capture des prix (commande de base) |
| `.\dev.ps1 run <sous-commande> [options]` | Lance le programme avec ses arguments |
| `.\dev.ps1 help` | Affiche l'aide |

## Utilisation

La commande de base est `.\dev.ps1 capture`: elle lance la capture avec les valeurs par défaut (base `prices.db`, serveur mémorisé, voir « Serveur de jeu »), et accepte `--db`, `--interface`, `--server` et `--verbose`. Pour les autres sous-commandes, `.\dev.ps1 run` transmet tout ce qui suit au programme: `.\dev.ps1 run prices` lance la sous-commande `prices`. `.\dev.ps1 capture` équivaut à `.\dev.ps1 run run`.

| Sous-commande | Effet | Exemple |
|---|---|---|
| `run` | Capture et enregistre les prix et statistiques de l'HDV (raccourci: `.\dev.ps1 capture`; `--verbose` affiche en direct les valeurs décodées) | `.\dev.ps1 capture --verbose` |
| `prices` | Derniers prix par objet, serveur et lot (`--item` pour filtrer) | `.\dev.ps1 run prices --item 307` |
| `history` | Historique des prix d'un objet pour un lot (`--lot` obligatoire: 1, 10, 100 ou 1000) | `.\dev.ps1 run history 307 --lot 10` |
| `stats` | Dernières statistiques d'un objet (`--period` parmi `24h`, `7d`, `30d`; toutes par défaut) | `.\dev.ps1 run stats 307 --period 7d` |
| `export-csv` | Exporte tous les prix en CSV (`--output` obligatoire) | `.\dev.ps1 run export-csv --output prix.csv` |
| `discover` | Journalise la structure des messages (voir plus bas) | `.\dev.ps1 run discover` |

Options communes: `--db` (base SQLite, défaut `prices.db`) pour `run`, `prices`, `history`, `stats` et `export-csv`; `--interface` (interface réseau à écouter, interface par défaut de Scapy si absent) pour `run` et `discover`. `--server NOM` (défaut: le serveur mémorisé, sinon la liste proposée au premier lancement, sinon `unknown`) et `--choose-server` n'existent que pour `run`, comme `--verbose` (affichage en direct des valeurs décodées). Les commandes de lecture n'ouvrent jamais une base absente: elles signalent l'erreur.

Pour capturer:

1. Lance `.\dev.ps1 capture` (ou `.\dev.ps1 capture --server Nom`) AVANT de te connecter au jeu. L'outil se resynchronise en cours de connexion, mais les premiers messages peuvent être manqués.
2. Joue, et ouvre les fiches d'objets dans l'HDV: seuls les objets consultés sont enregistrés.
3. Pour comparer avec l'écran du jeu en direct, ajoute `--verbose` (`.\dev.ps1 capture --verbose`): chaque message décodé affiche des tables de lots et de cours du marché dans la console.
4. Arrête avec Ctrl+C: la capture se termine proprement et la file d'écriture est vidée avant la sortie.

Piège PowerShell: une valeur contenant des virgules doit être entre guillemets, sinon PowerShell la découpe en tableau. Exemple: `--hex-types "jzs,ire"`.

## Noms d'objets (données)

`data/items.csv` est un index local `id -> nom` (colonnes `id,name_fr,level,type_fr`, trié par identifiant) construit à partir de l'API publique DofusDB (`api.dofusdb.fr`). Il sert de donnée de référence pour enrichir plus tard les prix; ailleurs dans l'outil, les objets restent identifiés par leur identifiant.

- Dans la fenêtre, ces données de référence (noms, serveurs, recettes, effets) se téléchargent toutes seules au lancement tant qu'elles manquent (`reference_data_missing`, un seul essai par lancement), puis sur le bouton de Réglages; le bloc d'état du menu affiche leur état et celui de la synchronisation. Le serveur de synchronisation se saisit dans Réglages par son nom de domaine seul (`https://` est ajouté, un chemin est refusé; `sync_server_url` dans `config.json`, prioritaire sur le `.env` et sur l'adresse intégrée).
- `.\dev.ps1 run names-update [--output chemin]` télécharge l'index. Comme `recipes-update`, `effects-update` et `servers-update`, elle ne fait que lire des données publiques de DofusDB, sur ordre (environ 430 requêtes); la capture reste hors ligne.
- `.\dev.ps1 run recipes-update` télécharge les recettes de craft (`data/recipes.csv`, environ 95 requêtes) pour l'onglet Craft.
- `.\dev.ps1 run effects-update` télécharge les effets des objets et les runes (`data/item_effects.csv`, `data/runes.csv`, environ 450 requêtes) pour la page Brisage (formule du poids de brisage, brisage classique et focus).
- Le fichier est local, régénérable et ignoré par git (`data/`). C'est une donnée destinée à l'outil, pas un fichier à ouvrir dans un tableur.

### Noms dans la base

- `.\dev.ps1 run names-import [--db prices.db] [--names data/items.csv]` remplace le contenu de la table `items` (`item_id`, `name_fr`, `level`, `type_fr`) de la base, en une seule transaction (relançable sans effet de bord). La base doit déjà exister; la commande n'en crée jamais. Elle affiche le nombre d'objets importés et les identifiants de la base absents de la référence (20 au plus).
- Trois vues sont créées avec le schéma: `lot_prices_named` (toutes les colonnes de `lot_prices` plus `item_name`, `item_level`, `item_type`), `market_stats_named` (idem pour `market_stats`, sans `points_json` pour rester léger) et `unknown_items` (un identifiant par ligne avec `lot_price_rows`, `stats_rows`, `first_seen`, `last_seen`). Un identifiant sans nom apparaît comme `N/A`.

Les commandes `prices`, `history`, `stats` et `export-csv` affichent aussi le nom et la catégorie de l'objet (colonnes `name`/`category`, `item_name`/`item_category` dans le CSV), lus dans la table `items`; `N/A` si l'objet n'y figure pas ou si les noms n'ont pas été importés (`names-import`).
- Exemple: `sqlite3 prices.db "SELECT item_name, lot_size, price, captured_at FROM lot_prices_named ORDER BY captured_at DESC LIMIT 10"`
- `.\dev.ps1 run names-gaps [--db prices.db]` affiche le contenu de `unknown_items` (les trous à investiguer). La capture (`run`) ne connaît toujours pas les noms et reste hors ligne.

## Liste des serveurs de jeu

`data/servers.csv` est une liste locale des serveurs de jeu (colonnes `id,name_fr,game_type_id,game_type_fr,community_id`, triée par identifiant), construite à partir de l'API publique DofusDB comme l'index des noms d'objets. Elle peut contenir des serveurs qui n'existent pas dans Dofus 3 (serveurs de tournoi, Kolizeum, etc.). La communauté reste un simple numéro.

- `.\dev.ps1 run servers-update [--output chemin]` télécharge la liste (quelques requêtes vers `api.dofusdb.fr`; la capture reste hors ligne).
- `.\dev.ps1 run servers [--servers data/servers.csv]` affiche un tableau `id  nom  type`, trié par type puis par nom.
- `names-import` charge aussi cette liste dans la table `servers` de la base (`server_id`, `name_fr`, `game_type_id`, `game_type_fr`, `community_id`), dans la même transaction que `items`. Sans fichier de serveurs, seuls les objets sont importés.
- `--server NOM` de `run` / `capture` (voir « Serveur de jeu ») est normalisé d'après la liste: `draconiros` devient `Draconiros`. Un nom absent de la liste est gardé tel quel avec un avertissement (jamais mémorisé). Sans fichier `data/servers.csv` (ou sans ligne valide), la liste intégrée des 13 serveurs classiques sert de repli: l'outil fonctionne sans `servers-update`. `unknown` n'avertit pas.
- `servers-update` ne garde par défaut que les serveurs classiques (`game_type_id` 0); `--all` garde tout. Le nombre de lignes reçues est vérifié contre le total de l'API AVANT ce filtre, puis les deux nombres sont affichés.

## Serveur de jeu

Chaque enregistrement porte le nom du serveur de jeu (Brial, Dakal...). Le trafic ne permet pas de le détecter: tu le choisis une fois dans la liste (celle de `data/servers.csv`, sinon la liste intégrée des serveurs classiques) et l'outil s'en souvient. Ordre de priorité:

1. `--server NOM` (`run` / `capture`): utilisé pour cette session seulement, jamais mémorisé, sans question.
2. Le serveur mémorisé, utilisé sans rien demander (un avertissement si son nom n'est plus dans la liste). Il s'applique à TOUTES les captures: si tu joues sur deux serveurs, passe `--server NOM` ou `--choose-server`; la ligne de démarrage affiche `(mémorisé ; --choose-server pour changer)` comme rappel.
3. Sinon, dans un terminal: une liste numérotée par type de jeu (numéro ou nom exact; Entrée passe). Le choix est mémorisé.
4. Sinon (sortie redirigée, pas de terminal): `unknown`, jamais mémorisé.

- `--choose-server` redemande le serveur même s'il est déjà mémorisé.
- `.\dev.ps1 run server` affiche le serveur mémorisé; `server --set NOM` le définit (seuls les noms de la liste sont acceptés, sans tenir compte de la casse; sinon erreur et `servers-update` pour la rafraîchir); `server --clear` l'oublie.
- Sans `data/servers.csv`, la liste intégrée des serveurs classiques est proposée: aucun nom libre n'est accepté ni mémorisé. Un `--server` vide est ignoré avec un avertissement. Une configuration ou une liste illisible n'interrompt jamais la capture.
- Le choix est stocké dans `%APPDATA%\OpenDofusData\config.json` (ailleurs: `~/.config/opendofusdata/config.json`); la variable d'environnement `OPENDOFUSDATA_CONFIG` donne un autre chemin complet. Un fichier corrompu est conservé en `config.json.corrupt` avant d'être remplacé.
- La détection automatique du serveur à partir du trafic est prévue, pas encore implémentée.

## Mode découverte et vie privée

`discover` écrit un journal JSON Lines (défaut `captures/discovery.jsonl`, option `--output`) qui sert à comprendre les messages d'une nouvelle version du jeu. Par défaut, chaque ligne contient l'heure, le sens, le type de message, la taille et la structure des champs (numéros, types, entiers, longueurs): ni texte ni octets.

| Option | Effet | Risque |
|---|---|---|
| `--include-text` | Ajoute des aperçus texte/hex (48 caractères, 32 octets) des valeurs opaques | Peut contenir du chat ou des identifiants |
| `--hex-types "jzs,ire"` | Aperçu hex (64 octets) et entiers compactés, uniquement pour les types de message nommés | Idem si un type transporte du chat |

Ces deux options affichent un avertissement au lancement. Relis le journal avant de le partager. Le journal est plafonné à 100 Mio (la capture s'arrête quand la limite est atteinte) et les lignes s'ajoutent à un fichier existant. `captures/` et `*.db` sont ignorés par git.

## Comment ça marche

1. Capture passive des paquets TCP du port 5555 avec Npcap/Scapy: l'outil ne modifie ni ne bloque rien.
2. Reconstruction des flux TCP (réordonnancement, resynchronisation en cours de connexion).
3. Découpage en messages Protobuf précédés de leur longueur, dans des enveloppes `type.ankama.com/<nom>`.
4. Décodage des messages utiles: pour l'HDV, les prix de lots (réponse à la consultation d'un objet) et les cours du marché (points des 24 heures et des 30 jours); pour le brisage, le résultat du concasseur; pour les familiers, l'inventaire, les objets ajoutés et les améliorations.
5. Écriture dans SQLite par un thread dédié.

Les règles ci-dessous concernent les statistiques de l'HDV.

Règles de calcul des statistiques:

- Médiane pondérée par les quantités vendues; moyenne = somme(prix x quantité) / somme(quantités), tronquée à l'entier.
- 24 h et 30 jours: points fournis par le serveur. 7 jours: aucun message dédié, calculé à partir des points des 30 jours dont l'horodatage est postérieur ou égal à minuit UTC de (date de capture - 7 jours).
- Horodatages stockés en UTC au format `YYYY-MM-DDTHH:MM:SSZ`.
- Dernière mise à jour des données = heure de capture (le serveur n'envoie pas ce champ).

Détails et octets vérifiés contre l'écran: [protocol-notes.md](protocol-notes.md). Capturer et valider de nouveaux cas: [new-categories.md](new-categories.md).

Suite prévue du projet: [roadmap.md](roadmap.md).

## Limites connues et maintenance

- Les noms courts des messages (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque mise à jour du jeu. Ils sont isolés dans `src/opendofusdata/messages.py`. Si l'outil ne décode plus rien après une mise à jour: lance `discover` avec `--hex-types` sur la nouvelle version, compare avec [protocol-notes.md](protocol-notes.md), puis mets à jour `messages.py`.
- L'HDV (prix de lots et cours du marché; pas d'achats, de ventes ni de changements de prix) est décodé. Brisage et familiers (bêta) le sont aussi, mais validés sur les captures d'un seul joueur: compare les vues Brisage et Familiers à l'écran du jeu. Les familiers demandent l'inventaire envoyé à la connexion pour identifier les ressources: lance l'outil avant de te connecter, ou déconnecte-toi puis reconnecte-toi une fois l'outil lancé. Tant que l'inventaire n'est pas reçu, les Logs signalent « reconnecte-toi au jeu » et une amélioration ignorée apparaît dans les Logs (« ressource inconnue » ou « familier inconnu », « ignorée », « reconnecte »).
- Fenêtre de 7 jours: la règle (minuit UTC sept jours avant la date de capture) est vérifiée à l'écran sur cinq objets.
- Un objet sans aucune offre (« Cet objet n'est pas en vente actuellement ») ne produit aucun enregistrement, par décision: l'absence de relevé ne signifie pas prix 0, le dernier prix connu garde son horodatage d'origine.
- Le serveur de jeu n'apparaît pas dans les messages: c'est le joueur qui le choisit (voir « Serveur de jeu »).
- Dans Windows PowerShell 5.1, l'aide française de `dev.ps1` peut afficher des accents cassés (encodage du script).

## Versions

Le numéro de version (`MAJEUR.MINEUR.CORRECTIF`) est défini à un seul endroit: `__version__` dans `src/opendofusdata/__init__.py`. `pyproject.toml` et la page À propos le lisent. Pour publier une version: modifie ce numéro, mets à jour la feuille de route, commite sur `main`, puis crée le tag `vX.Y.Z` (par exemple `git tag -a v1.0.1 -m "v1.0.1"`).

## Serveur de clés

Le dossier `src/server/` contient un petit serveur HTTP (FastAPI) qui n'accepte que les requêtes portant une clé signée valide. Il est indépendant du client: son propre venv (`src/server/.venv`), ses dépendances verrouillées (`requirements.lock` pour l'exécution, `requirements-dev.lock` avec les outils de test pour le venv de dev; même méthode que le client) et ses tests, qui se lancent avec `.\src\server\dev.ps1 test` et dans le workflow CI (job `server-test`).

- **Clés:** une clé est un jeton `odk1.<identifiant>.<signature>`, la signature étant un HMAC-SHA256 de l'identifiant avec un secret maître. Le serveur ne stocke aucune clé: il recalcule la signature à chaque requête et ne garde que la liste des identifiants révoqués.
- **Secret maître:** `.\src\server\dev.ps1 new-secret` en génère un et affiche deux lignes: `KEY_SECRET=...` pour `src/server/.env` et `ADMIN_SECRET=...` pour le `.env` de l'administrateur (jamais versionnés). Sans secret valide (43 caractères au moins), le serveur refuse de démarrer.
- **Lancement local:** `.\src\server\dev.ps1 run` (lit `src/server/.env`, écoute sur 127.0.0.1:8000). La base des révocations est `src/server/keys.db`, ou le fichier donné par `KEYSERVER_DB`.
- **Authentification:** en-tête `Authorization: Bearer <clé>`; toute erreur (absente, mal formée, mal signée, révoquée) donne le même `401`.

## Synchronisation et administration (client)

Côté application, trois fonctions parlent au serveur de clés: le test de connexion et l'administration sur action explicite, la synchronisation des prix seulement si le joueur l'a cochée (voir « Synchronisation des prix »).

### Clé de synchronisation et test de connexion

Dans Réglages, la carte *Synchronisation* garde la clé du joueur dans `config.json` (`sync_api_key`, champ masqué) et propose *Tester la connexion*: un `GET /check` avec `Authorization: Bearer <clé>`, en HTTPS seulement, sans suivre de redirection, avec un délai et une taille de réponse bornés (`https_json.py`). Rien ne part sans clic. L'adresse du serveur est `DEFAULT_SERVER_URL` (`sync_client.py`, à renseigner quand le domaine existe) ou `SERVER_URL` dans le `.env` placé à côté de `config.json`; sans adresse, le bouton de test est désactivé. Le format de clé (`sync_key.py`) est recopié du serveur et verrouillé par la même clé de test dans les deux suites.

### Onglet Administration

Un onglet *Administration* apparaît (en dernier dans le menu) seulement si le `.env` placé à côté de `config.json` contient `ADMIN_SECRET` (43 caractères au moins, la valeur donnée par `new-secret`) et si une adresse de serveur est connue (`SERVER_URL` ou `DEFAULT_SERVER_URL`). Sans cela l'onglet n'existe pas et rien n'est envoyé. L'onglet n'est qu'un confort: le serveur vérifie le jeton d'administration à chaque appel.

- **Générer:** un pseudo, un clic. La clé est calculée sur ce PC (`admin_keys.py`, aucun appel réseau) et affichée avec un bouton *Copier*. Le registre `admin_keys.json` (à côté du `.env`) note le pseudo, l'identifiant et la date, jamais la clé: elle se recalcule avec *Copier la clé*. Sauvegarde ce fichier: sans lui, les clés déjà données restent valables, mais tu ne sais plus à qui. Pour repartir de zéro, génère un nouveau secret (`new-secret`) et remplace-le des deux côtés: toutes les clés sont alors à refaire.
- **Révoquer (avec ou sans suppression des relevés de la clé):** après confirmation, l'application envoie l'identifiant au serveur (`POST /admin/revoke`, `Authorization: Bearer <jeton d'administration>` dérivé du secret, jamais le secret). La ligne n'est marquée révoquée qu'après la réponse `200`; en cas d'échec le registre reste inchangé.

## Synchronisation des prix

Les joueurs envoient les prix de lots de l'HDV, les brisages, les améliorations de familiers qu'ils observent et l'XP qu'ils saisissent à la main pour une ressource, et récupèrent ceux des autres (seuls les favoris restent locaux). Une saisie est un instantané des totaux (ressources, XP) d'une ressource: le dernier de chaque joueur compte, 0 et 0 l'efface, et les totaux de tous les joueurs s'additionnent. Le serveur ne garde que le dernier instantané par clé et ressource (1000 au plus par clé) et ne le purge pas avec la rétention de 14 jours; route `/saisies` (`/saisies/mine` pour la restauration).

**Serveur** (routes authentifiées par clé utilisateur, jamais par le jeton d'administration):

| Route | Rôle |
|---|---|
| `POST /readings` | Envoie 1 à 2000 relevés `{server, item_id, lot_size, price, observed_at}`; réponse `{accepted, duplicates}` (un relevé déjà reçu est un doublon, pas une erreur) |
| `GET /readings?since=N&limit=L` | Relevés des autres clés arrivés après le numéro d'ordre N (`limit` de 1 à 2000); réponse `{readings, next}`; chaque relevé porte `seq` et `key_id` |
| `POST /brisages`, `POST /familiers` | Envoie 1 à 2000 événements `{events: [...]}`: un objet brisé (`server, item_id, quantity, coefficient, runes [[id, quantité]...], observed_at`) ou une amélioration de familier (`server, pet_item_id, resources [[id, quantité]...], before, after {level, experience, experience_max, prospection}, observed_at`); réponse `{accepted, duplicates}` |
| `GET /brisages?since=N&limit=L`, `GET /familiers?since=N&limit=L` | Événements des autres clés après le numéro d'ordre N; réponse `{events, next}` (chaque événement porte `seq` et `key_id`) |
| `GET /brisages/mine?after=K&limit=L`, `GET /familiers/mine?after=K&limit=L` | Les événements envoyés par la clé elle-même (restauration sur une base neuve) |
| `GET /readings/mine?after=K&limit=L` | Les relevés envoyés par la clé elle-même (restauration de son historique sur une base neuve), par pages; réponse `{readings, next}` |
| `GET /readings/latest?after=K&limit=L` | Premier lancement d'un joueur: dernier relevé de chaque (serveur, objet, lot) des autres clés, par pages; réponse `{readings, next, as_of, done}` |

- **Paramètres de requête:** le garde-fou n'accepte, pour ces deux routes `GET`, que les paramètres déclarés, chacun une seule fois, en entiers décimaux de 1 à 12 chiffres, sans encodage en pourcentage; tout le reste donne `400`. Un `GET` avec un corps est refusé. **Toute route ajoutée doit être déclarée dans `ALLOWED_ROUTES`.**
- **Identité:** `key_id` est le code de 11 caractères de la clé émettrice, un pseudonyme (jamais la clé, sa signature ni le pseudo de l'administrateur). Il permet de révoquer une clé et, au choix, de supprimer ses relevés. Les relevés d'une clé ne lui sont jamais renvoyés.
- **Rétention:** 14 jours, purge quotidienne (aussi au démarrage), sur la date d'observation. Base: le même fichier que la liste des révocations (`keys.db`).
- **Révocation:** `POST /admin/revoke` accepte `{"key_id": "...", "purge": true|false}` (`false` par défaut). La clé est révoquée d'abord, puis ses relevés sont supprimés si `purge` est vrai; réponse `{"revoked": true, "purged": n}`. Sans purge, les relevés restent servis jusqu'à la fin de la rétention.
- **Limite connue (voulue):** une purge côté serveur ne retire pas ce que les clients ont déjà récupéré (`source_key_id` rendrait possible une propagation plus tard).

**Client:**

- **Réglages, carte Synchronisation:** pas de case à cocher: enregistrer une clé (avec une adresse de serveur) active l'envoi et la récupération, la retirer les arrête (un ancien `sync_send` ou `sync_receive` dans `config.json` est ignoré). Un fil d'arrière-plan lance un tour toutes les 10 secondes (attente doublée, plafonnée à 1 heure, tant que le serveur est injoignable; pause tant que la clé refusée n'a pas été remplacée) et relit les réglages à chaque tour.
- **Brisages et familiers:** même mécanisme que les prix, sans instantané « derniers » (un événement n'a pas de dernier état): un journal `events` côté serveur (`kind`, `key_id`, date, charge JSON canonique, doublons ignorés), rétention de 14 jours, purge avec la clé; côté client `broken_items` et `pet_feedings` gagnent `origin`, `synced_at` et `source_key_id`, les curseurs `events_broken_cursor` et `events_pet_cursor` sont dans `sync_state`, la restauration de l'historique propre se fait une fois par type (`events_*_own_done`) et un échec de cette étape n'arrête pas la suite. Les valeurs reçues sont validées comme celles du serveur (`event_rules.py`).
- **Base locale:** `lot_prices` gagne `origin` (`local` ou `remote`), `synced_at` et `source_key_id`; la table `sync_state` garde le curseur. Les bases existantes sont migrées sans perte. Un prix identique au dernier relevé réellement envoyé depuis moins d'une heure pour la même clé n'est pas renvoyé, et rien de plus vieux que 14 jours ni de refusé d'avance par le serveur (prix, nom de serveur) n'est envoyé. Si l'envoi échoue (par exemple un `422` quand l'heure du PC est fausse), la récupération continue. Les relevés reçus ne sont jamais renvoyés.
- **Récupération:** au premier tour `GET /readings/latest` page par page, puis seulement `GET /readings` depuis le curseur. Une seule fois par base, en dernier, `GET /readings/mine` rend au joueur ses propres relevés des 14 derniers jours (enregistrés comme locaux et déjà envoyés, sans doublon avec ce qu'il a déjà); un échec de cette étape n'empêche pas la récupération des prix des autres. Tout ce que le serveur renvoie est validé avant insertion (types, bornes, nom de serveur sans symbole ni caractère invisible), les boucles de pages sont plafonnées, le snapshot interrompu reprend où il s'était arrêté et `reset-data` remet la position de synchro à zéro.
- **Purge locale optionnelle:** carte *Données locales* (case « au lancement » décochée par défaut, `purge_old_data`, et bouton *Purger maintenant* avec confirmation). Supprime les lignes de `lot_prices` et `market_stats` de plus de 14 jours en gardant toujours la plus récente de chaque (objet, serveur, lot) ou (objet, serveur, période). Ne touche jamais aux favoris et observations manuelles de familiers (dans `config.json`), ni aux noms, serveurs, brisages, améliorations de familiers et à l'état de synchro.
- **Administration:** pour chaque clé, *Révoquer* ou *Révoquer et supprimer ses relevés*, chacune avec sa confirmation.

## Tests et conventions

```powershell
.\dev.ps1 test
```

Les tests `pytest` utilisent des données synthétiques. Ceux du serveur ont leur propre commande: `.\src\server\dev.ps1 test`. Un test de style (`tests/test_text_style.py`) interdit dans les textes les tirets typographiques longs et le point médian. Conventions de code (fonctions de 20 lignes maximum, modules de 200 lignes maximum, annotations de type): voir [CLAUDE.md](../CLAUDE.md).

## Remise à zéro des données

`.\dev.ps1 run reset-data --yes` (ou `opendofusdata reset-data --yes`) sauvegarde la base en `<nom>-backup-AAAAMMJJ-HHMMSS.db` à côté d'elle, puis efface les prix, statistiques, brisages et améliorations de familiers. Les noms d'objets et les serveurs sont gardés. Sans `--yes`, la commande n'efface rien.

