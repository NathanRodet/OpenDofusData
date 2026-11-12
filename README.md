# OpenDofusData

Outil local pour Windows qui capture passivement le trafic réseau de Dofus 3 (TCP 5555) avec Npcap et Scapy, décode les messages utiles et les stocke dans une base SQLite locale. Objectif global: ce client récolte les données, les stocke en SQLite, puis alimentera à terme un serveur distant (synchronisation et serveur hors périmètre de la v1). La v1 n'envoie rien à l'extérieur.

**Version actuelle : 2.0.0** (refonte de la fenêtre: tableaux, filtres par période, estimations de brisage et de familiers; tout est collecté en permanence). Elle est affichée dans Réglages.

## Données collectées

L'outil collecte en permanence trois catégories de données, sans interrupteur: tout ce qui est capté est enregistré, avec sa date (voir [docs/roadmap.md](docs/roadmap.md)).

| Catégorie | Contenu | État |
|---|---|---|
| Données HDV | Prix des lots et cours du marché | Disponible |
| Taux de recyclage des ressources | Pas de capture réseau: le taux à 100 % de chaque objet (`recycling_nuggets`, DofusDB) est une colonne de `data/items.csv`, téléchargée avec les noms (« Télécharger les noms ») | Disponible |
| Données de brisage | Objets détruits au Concasseur, coefficient et runes obtenues, un enregistrement par concassage | Disponible, à vérifier en jeu |
| Données d'expérience des familiers (pets) | Ressources données à un familier et son état avant et après (niveau, expérience, prospection) | Disponible, à vérifier en jeu; demande de lancer l'outil avant la connexion |

## Ce que fait l'outil (catégorie HDV)

- Prix des lots de 1, 10, 100 et 1000 (prix total du lot).
- Statistiques du marché sur 24 h, 7 jours et 30 jours: médiane, moyenne, objets vendus, dernier achat, et heure de mise à jour des données.
- Tout est stocké avec l'historique complet dans SQLite (`prices.db` par défaut).
- Les objets sont identifiés par leur identifiant seulement: le trafic ne contient pas les noms.

## Installer et lancer (joueurs)

1. Installe [Npcap](https://npcap.com) (Windows 11). Il n'est pas fourni avec OpenDofusData. Ne coche pas « Restrict Npcap driver's access to Administrators only », sinon lance OpenDofusData en administrateur. Le mode « WinPcap API-compatible » n'est pas nécessaire.
2. Télécharge `OpenDofusData.exe` depuis la page [Releases](https://github.com/NathanRodet/OpenDofusData/releases). `OpenDofusData.exe.sha256` contient son empreinte SHA-256 si tu veux la vérifier (`Get-FileHash OpenDofusData.exe`).
3. Double-clique sur `OpenDofusData.exe`, de préférence AVANT de te connecter au jeu. Le programme n'est pas signé: Windows peut afficher « Windows a protégé votre ordinateur » (SmartScreen). Clique sur « Informations complémentaires » puis « Exécuter quand même ».
4. Dans la page **Réglages**, choisis ton serveur de jeu (le trafic ne permet pas de le deviner). La capture redémarre toute seule avec ce choix. Facultatif: « Télécharger les noms » pour voir les noms d'objets dans les logs.

Aucune installation de Python n'est nécessaire. Les données (`prices.db`), la configuration (`config.json`) et le journal technique (`opendofusdata.log`) sont dans `%APPDATA%\OpenDofusData`.

## La fenêtre OpenDofusData

Thème sombre, pleine taille et responsive (minimum 760×480, ouverture en 1280×800). Menu de 220 px à gauche, avec en bas l'état de la capture (active, arrêtée ou erreur avec un message clair, par exemple Npcap absent ou droits insuffisants), le serveur, les compteurs de la session, l'heure du dernier relevé et le bouton « Arrêter » / « Relancer ». Fermer la fenêtre arrête aussi la capture. Elle peut rester ouverte en arrière-plan pendant que tu joues. Pas de démarrage automatique avec Windows.

Chaque vue de données lit la base locale (en lecture seule), n'affiche que le serveur choisi dans Réglages, et se filtre par période (Dernière heure, 6 heures, Aujourd'hui, 7 jours, 30 jours, Tout, Personnalisé; « Aujourd'hui » commence à minuit, heure locale). Les dates des tableaux sont relatives (« il y a 12 min »), la date exacte est dans le détail. Le tableau est triable (clic sur l'en-tête) et affiche au plus 5 000 lignes.

| Page | Contenu |
|---|---|
| HDV | Un tableau par objet (dernier prix ×1, médian 24 h, vendus 24 h, dernier relevé), recherche par nom, détail avec courbes datées 24 h / 7 j / 30 j, lots ×1/×10/×100 et historique des relevés |
| Brisage | Un tableau par objet brisé: coefficient, valeur estimée de l'objet (moyenne 24 h), valeur HDV de l'objet (dernier prix), valeur estimée des runes et plus-value (triée de la meilleure à la pire); détail avec l'historique du coefficient |
| Familiers | Un tableau par ressource donnée: prix d'une ressource, XP pour 1 ressource, kamas par XP (trié du moins cher au plus cher), observations, coût pour monter un familier (179 591 XP); les trois meilleures lignes sont en vert; détail avec la courbe du prix au fil du temps |
| Logs | Les 200 dernières données captées en direct (heure, type, objet, détail, valeur), filtrables par type, période et nom; « Vider » ne vide que la liste, jamais la base |
| Réglages | Serveur de jeu et emplacement de la base (un changement relance la capture), téléchargement des noms d'objets, prix utilisé pour les estimations (Dernier prix HDV par défaut, Médian 24 h ou Moyen 24 h), mises à jour, à propos |

### Mises à jour

Jamais automatiques. Au démarrage, le programme demande à GitHub si une version plus récente existe (une requête anonyme, voir « Confidentialité »; désactivable dans Réglages). S'il y en a une, un point bleu apparaît à côté de « Réglages ». Dans la carte « Mises à jour », « Mettre à jour et relancer » télécharge `OpenDofusData.exe`, vérifie son empreinte SHA-256 contre `OpenDofusData.exe.sha256`, remplace le programme et le relance. Une version sans ces deux fichiers, ou un programme lancé depuis les sources, propose seulement « Voir la version » (la page de la Release). L'empreinte protège contre un fichier corrompu; comme le programme n'est pas signé, elle ne prouve pas son auteur: ne mets à jour que depuis les Releases de ce dépôt.

### Réglages enregistrés

La fenêtre écrit dans `config.json` (voir « Serveur de jeu »): `server`, `database_path` (priorité: `--db`, puis `database_path`, puis `prices.db`; avec le programme packagé, `%APPDATA%\OpenDofusData\prices.db`), `price_mode` (`last` par défaut, `median` ou `mean`) et `check_updates` (booléen, défaut vrai). Une ancienne clé `enabled_categories` est ignorée.

### Remise à zéro des données

`.\dev.ps1 run reset-data --yes` (ou `opendofusdata reset-data --yes`) sauvegarde la base en `<nom>-backup-AAAAMMJJ-HHMMSS.db` à côté d'elle, puis efface les prix, statistiques, brisages et améliorations de familiers. Les noms d'objets et les serveurs sont gardés. Sans `--yes`, la commande n'efface rien.

## Pour les développeurs: prérequis

- Windows 11
- Python 3.13
- [Npcap](https://npcap.com) (voir plus haut)
- Dofus 3 lancé sur la même machine que l'outil.

## Pour les développeurs: installation

Depuis PowerShell, à la racine du projet:

```powershell
.\dev.ps1 setup
```

Cette commande crée le venv `.venv` et installe `requirements.txt` (`scapy` pour la capture, `customtkinter` pour la fenêtre, `pytest` pour les tests, `pyinstaller` pour l'exécutable; le décodage Protobuf et SQLite utilisent la bibliothèque standard). Si PowerShell refuse d'exécuter le script, lance une fois `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Npcap étant installé au niveau du système, il fonctionne depuis le venv sans configuration.

Le projet est aussi un paquet Python (`pyproject.toml`). Dans le venv, `pip install -e .` installe la commande `opendofusdata`, équivalente à `python -m opendofusdata` (ex. `opendofusdata window`, `opendofusdata run --server Kourial`). `.\dev.ps1 setup` fait cette installation. Au premier lancement de `window` ou `run` dans un terminal, la liste des serveurs de jeu est proposée (le choix est mémorisé, voir « Serveur de jeu »); `--server NOM` et `--choose-server` fonctionnent aussi.

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

Pour le fonctionnement normal (`capture` / `run` et la base de données), l'outil ne garde que des données de jeu des catégories ci-dessus (HDV, brisage, familiers): identifiants d'objets, prix, quantités, horodatages et nom du serveur de jeu choisi par le joueur. Tout est collecté en permanence et rien n'est envoyé. Il ne stocke ni n'envoie jamais d'adresses IP, de comptes, de noms de personnages ni de chat (il utilise les adresses en mémoire pour suivre les connexions, sans les écrire). Le mode découverte optionnel avec `--include-text` ou `--hex-types` (désactivé par défaut, voir plus bas) peut écrire du texte issu des messages (éventuellement du chat ou des identifiants) dans un journal LOCAL que le joueur relit avant de le partager. Aucune donnée de jeu ne quitte ta machine dans cette version; l'envoi prévu vers un serveur distant ne transmettra que ces mêmes données de jeu. Les seules requêtes réseau du programme: la vérification des mises à jour au démarrage (une requête anonyme à api.github.com, sans identifiant; désactivable dans Réglages), et, seulement si tu cliques sur « Télécharger les noms » (ou lances `names-update`), le téléchargement des noms d'objets depuis api.dofusdb.fr. Le code source est public pour que ce comportement puisse être vérifié.

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
- L'HDV (prix de lots et cours du marché; pas d'achats, de ventes ni de changements de prix) est décodé. Brisage et familiers (bêta) le sont aussi, mais validés sur les captures d'un seul joueur: compare les vues Brisage et Familiers à l'écran du jeu. Les familiers demandent l'inventaire envoyé à la connexion pour identifier les ressources: lance l'outil avant de te connecter, ou déconnecte-toi puis reconnecte-toi une fois l'outil lancé. Tant que l'inventaire n'est pas reçu, les Logs signalent « reconnecte-toi au jeu » et une amélioration ignorée apparaît dans les Logs (« ressource inconnue » ou « familier inconnu », « ignorée », « reconnecte »).
- Fenêtre de 7 jours: la règle (minuit UTC sept jours avant la date de capture) est vérifiée à l'écran sur cinq objets.
- Un objet sans aucune offre (« Cet objet n'est pas en vente actuellement ») ne produit aucun enregistrement, par décision: l'absence de relevé ne signifie pas prix 0, le dernier prix connu garde son horodatage d'origine.
- Le serveur de jeu n'apparaît pas dans les messages: c'est le joueur qui le choisit (voir « Serveur de jeu »).
- Dans Windows PowerShell 5.1, l'aide française de `dev.ps1` peut afficher des accents cassés (encodage du script).

## Licence

Tous droits réservés. Le code est publié sur GitHub pour être consulté et vérifié, mais aucune licence n'autorise à le réutiliser, le modifier ni le redistribuer sans l'accord de l'auteur.

## Versions

Le numéro de version (`MAJEUR.MINEUR.CORRECTIF`) est défini à un seul endroit: `__version__` dans `src/opendofusdata/__init__.py`. `pyproject.toml` et la page À propos le lisent. Pour publier une version: modifie ce numéro, mets à jour la feuille de route, commite sur `main`, puis crée le tag `vX.Y.Z` (par exemple `git tag -a v1.0.1 -m "v1.0.1"`).

## Tests et conventions

```powershell
.\dev.ps1 test
```

Les tests `pytest` utilisent des données synthétiques. Conventions de code (fonctions de 20 lignes maximum, modules de 200 lignes maximum, annotations de type): voir [CLAUDE.md](CLAUDE.md).
