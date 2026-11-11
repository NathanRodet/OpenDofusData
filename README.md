# OpenDofusData

Outil local pour Windows qui capture passivement le trafic réseau de Dofus 3 (TCP 5555) avec Npcap et Scapy, décode les messages utiles et les stocke dans une base SQLite locale. Objectif global: ce client récolte les données, les stocke en SQLite, puis alimentera à terme un serveur distant (synchronisation et serveur hors périmètre de la v1). La v1 n'envoie rien à l'extérieur.

**Version actuelle : 1.0.0** (la v1 : capture locale de l'HDV, fenêtre joueur). Elle est affichée dans la page À propos de la fenêtre.

## Données collectées

L'outil est conçu pour collecter quatre catégories de données. Chacune pourra être désactivée séparément par le joueur (voir [docs/roadmap.md](docs/roadmap.md)).

| Catégorie | Contenu | État |
|---|---|---|
| Données HDV | Prix des lots et cours du marché | Disponible (v1) |
| Données de recyclage des ressources | Ressources obtenues en recyclant | Prévu, pas encore décodé |
| Données de brisage | Résultats de brisage | Prévu, pas encore décodé |
| Données d'expérience des familiers (pets) | Expérience et ressources des familiers | Prévu, pas encore décodé |

Tant que les autres décodeurs n'existent pas, seule la catégorie HDV est enregistrée.

## Ce que fait l'outil (v1, catégorie HDV)

- Prix des lots de 1, 10, 100 et 1000 (prix total du lot).
- Statistiques du marché sur 24 h, 7 jours et 30 jours: médiane, moyenne, objets vendus, dernier achat, et heure de mise à jour des données.
- Tout est stocké avec l'historique complet dans SQLite (`prices.db` par défaut).
- Les objets sont identifiés par leur identifiant seulement: le trafic ne contient pas les noms.

## Prérequis

- Windows 11
- Python 3.13
- [Npcap](https://npcap.com) 1.90, à installer toi-même depuis npcap.com (il n'est pas fourni avec OpenDofusData), au niveau du système. Ne pas cocher « Restrict Npcap driver's access to Administrators only », sinon l'outil doit être lancé dans un terminal administrateur (c'est aussi la solution si la capture échoue faute de droits). Le mode « WinPcap API-compatible » n'est pas nécessaire.
- Dofus 3 lancé sur la même machine que l'outil.

## Installation

Depuis PowerShell, à la racine du projet:

```powershell
.\dev.ps1 setup
```

Cette commande crée le venv `.venv` et installe `requirements.txt` (`scapy` pour la capture, `customtkinter` pour la fenêtre, `pytest` pour les tests; le décodage Protobuf et SQLite utilisent la bibliothèque standard). Si PowerShell refuse d'exécuter le script, lance une fois `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Npcap étant installé au niveau du système, il fonctionne depuis le venv sans configuration.

Le projet est aussi un paquet Python (`pyproject.toml`). Dans le venv, `pip install -e .` installe la commande `opendofusdata`, équivalente à `python -m opendofusdata` (ex. `opendofusdata run --server Kourial`). `.\dev.ps1 setup` fait cette installation.

## Fenêtre OpenDofusData (utilisation pour les joueurs)

1. Installe Npcap depuis npcap.com (voir « Prérequis »; le mode « WinPcap API-compatible » n'est pas nécessaire).
2. Lance `opendofusdata window` (ou `python -m opendofusdata window`) AVANT de te connecter au jeu. Au tout premier lancement, la console te propose la liste des serveurs de jeu (le choix est mémorisé, voir « Serveur de jeu »); `--server NOM` et `--choose-server` fonctionnent aussi.
3. La fenêtre OpenDofusData s'ouvre et lance la capture. Thème sombre, menu à gauche, cinq pages. Elle est redimensionnable (minimum 640×400); la page reste dans une colonne centrée.
4. « Arrêter » (en bas du menu) stoppe proprement la capture, le bouton devient « Relancer »; fermer la fenêtre l'arrête aussi. La fenêtre peut rester ouverte en arrière-plan pendant que tu joues. Pas de démarrage automatique avec Windows.

| Page | Contenu |
|---|---|
| Accueil | État (Capture active, arrêtée ou erreur avec un message clair, par exemple Npcap absent ou droits insuffisants), serveur, enregistrements de la session, heure du dernier relevé, « Voir les prix en ligne » (adresse provisoire tant que le serveur n'existe pas) |
| Données | Une ligne par catégorie (HDV, recyclage, brisage, pets) avec un interrupteur. Seule l'HDV est décodée aujourd'hui, les autres sont « bientôt ». Désactiver une catégorie arrête de l'enregistrer tout de suite |
| Logs | Interrupteur « Afficher les logs », désactivé par défaut. Activé, il affiche en colonnes (heure, type, objet, détail, valeur) les 200 dernières données captées. Désactivé, rien n'est affiché ni gardé |
| Réglages | Serveur de jeu et emplacement de la base de données. S'appliquent au prochain démarrage de la capture (arrête puis relance) |
| À propos | Version, ce qui est collecté, lien vers le dépôt |

Les réglages de la fenêtre sont écrits dans `config.json` (voir « Serveur de jeu »): `server`, `database_path` (priorité: `--db`, puis `database_path`, puis `prices.db`) et `enabled_categories` (liste, par défaut `["hdv"]`). Les données vont dans `prices.db` (dossier courant) tant que tu n'as pas changé l'emplacement. Rien n'est envoyé nulle part.

Les droits administrateur ne sont nécessaires que si Npcap a été installé avec « Restrict Npcap driver's access to Administrators only »: dans ce cas lance la commande dans un terminal administrateur.

## Script de dev

| Commande | Effet |
|---|---|
| `.\dev.ps1 setup` | Crée le venv et installe les dépendances |
| `.\dev.ps1 test` | Lance `pytest` dans le venv |
| `.\dev.ps1 clean` | Supprime le venv et les caches |
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

- `.\dev.ps1 run names-update [--output chemin]` télécharge l'index. C'est la seule commande qui accède au réseau, et une seule fois (environ 430 requêtes); la capture reste hors ligne.
- Le fichier est local, régénérable et ignoré par git (`data/`). C'est une donnée destinée à l'outil, pas un fichier à ouvrir dans un tableur.

### Noms dans la base

- `.\dev.ps1 run names-import [--db prices.db] [--names data/items.csv]` remplace le contenu de la table `items` (`item_id`, `name_fr`, `level`, `type_fr`) de la base, en une seule transaction (relançable sans effet de bord). La base doit déjà exister; la commande n'en crée jamais. Elle affiche le nombre d'objets importés et les identifiants de la base absents de la référence (20 au plus).
- Trois vues sont créées avec le schéma: `lot_prices_named` (toutes les colonnes de `lot_prices` plus `item_name`, `item_level`, `item_type`), `market_stats_named` (idem pour `market_stats`, sans `points_json` pour rester léger) et `unknown_items` (un identifiant par ligne avec `lot_price_rows`, `stats_rows`, `first_seen`, `last_seen`). Un identifiant sans nom apparaît comme `N/A`.

Les commandes `prices`, `history`, `stats` et `export-csv` affichent aussi le nom et la catégorie de l'objet (colonnes `name`/`category`, `item_name`/`item_category` dans le CSV), lus dans la table `items`; `N/A` si l'objet n'y figure pas ou si les noms n'ont pas été importés (`names-import`).
- Exemple: `sqlite3 prices.db "SELECT item_name, lot_size, price, captured_at FROM lot_prices_named ORDER BY captured_at DESC LIMIT 10"`
- `.\dev.ps1 run names-gaps [--db prices.db]` affiche le contenu de `unknown_items` (les trous à investiguer). La capture (`run`) ne connaît toujours pas les noms et reste hors ligne.

## Serveurs de jeu

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

## Confidentialité

Pour le fonctionnement normal (`capture` / `run` et la base de données), l'outil ne garde que des données de jeu des catégories ci-dessus (aujourd'hui l'HDV): identifiants d'objets, prix, quantités, horodatages et nom du serveur de jeu choisi par le joueur. Le joueur pourra désactiver chaque catégorie (collecte et envoi). Il ne stocke ni n'envoie jamais d'adresses IP, de comptes, de noms de personnages ni de chat (il utilise les adresses en mémoire pour suivre les connexions, sans les écrire). Le mode découverte optionnel avec `--include-text` ou `--hex-types` (désactivé par défaut, voir plus bas) peut écrire du texte issu des messages (éventuellement du chat ou des identifiants) dans un journal LOCAL que le joueur relit avant de le partager. Rien ne quitte ta machine dans cette version; l'envoi prévu vers un serveur distant ne transmettra que ces mêmes données de jeu. L'outil est libre et open source: son comportement peut être vérifié dans le code.

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
4. Décodage de deux messages: les prix de lots (réponse à la consultation d'un objet) et les cours du marché (points des 24 heures et des 30 jours).
5. Écriture dans SQLite par un thread dédié.

Règles de calcul des statistiques:

- Médiane pondérée par les quantités vendues; moyenne = somme(prix x quantité) / somme(quantités), tronquée à l'entier.
- 24 h et 30 jours: points fournis par le serveur. 7 jours: aucun message dédié, calculé à partir des points des 30 jours dont l'horodatage est postérieur ou égal à minuit UTC de (date de capture − 7 jours).
- Horodatages stockés en UTC au format `YYYY-MM-DDTHH:MM:SSZ`.
- Dernière mise à jour des données = heure de capture (le serveur n'envoie pas ce champ).

Détails et octets vérifiés contre l'écran: [docs/protocol-notes.md](docs/protocol-notes.md).

Suite prévue du projet: [docs/roadmap.md](docs/roadmap.md).

## Limites connues et maintenance

- Les noms courts des messages (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque mise à jour du jeu. Ils sont isolés dans `src/opendofusdata/messages.py`. Si l'outil ne décode plus rien après une mise à jour: lance `discover` avec `--hex-types` sur la nouvelle version, compare avec `docs/protocol-notes.md`, puis mets à jour `messages.py`.
- Seule la catégorie HDV est décodée (prix de lots et cours du marché): pas d'achats, de ventes ni de changements de prix, et pas d'affichage en direct. Recyclage, brisage et expérience des familiers sont prévus mais pas encore décodés.
- Fenêtre de 7 jours: la règle (minuit UTC sept jours avant la date de capture) est vérifiée à l'écran sur cinq objets.
- Un objet sans aucune offre (« Cet objet n'est pas en vente actuellement ») ne produit aucun enregistrement, par décision: l'absence de relevé ne signifie pas prix 0, le dernier prix connu garde son horodatage d'origine.
- Le serveur de jeu n'apparaît pas dans les messages: c'est le joueur qui le choisit (voir « Serveur de jeu »).
- Dans Windows PowerShell 5.1, l'aide française de `dev.ps1` peut afficher des accents cassés (encodage du script).

## Versions

Le numéro de version (`MAJEUR.MINEUR.CORRECTIF`) est défini à un seul endroit: `__version__` dans `src/opendofusdata/__init__.py`. `pyproject.toml` et la page À propos le lisent. Pour publier une version: modifie ce numéro, mets à jour la feuille de route, commite sur `main`, puis crée le tag `vX.Y.Z` (par exemple `git tag -a v1.0.1 -m "v1.0.1"`).

## Tests et conventions

```powershell
.\dev.ps1 test
```

Les tests `pytest` utilisent des données synthétiques. Conventions de code (fonctions de 20 lignes maximum, modules de 200 lignes maximum, annotations de type): voir [CLAUDE.md](CLAUDE.md).
