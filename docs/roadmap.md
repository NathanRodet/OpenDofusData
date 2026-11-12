# Feuille de route

État au 2026-11-13: la V2 (refonte de la fenêtre) est développée. Version du produit: 2.0.0 (tag `v1.0.0` publié; `v1.1.0` et `v2.0.0` à publier sur décision du propriétaire).

## Validé en jeu

- Fenêtre des 7 jours: confirmée sur cinq objets, dont le Filet multiplicateur de Dragodinde (11 630 / 12 253 / 112). Les lignes 7 jours de la base locale ont été recalculées (sauvegarde `data/prices.backup-before-7d-recompute.db`).
- Capture en direct avec la fenêtre (objets réels visibles dans les logs), et exécutable packagé: il s'ouvre, capture, journalise dans `%APPDATA%\OpenDofusData` et se ferme proprement.

## Fait

- **Fenêtre du client (V2):** `opendofusdata window`, fenêtre CustomTkinter pleine taille et responsive, menu HDV / Brisage / Familiers / Logs / Réglages, tableaux triables, filtres par période, détails avec courbes datées, estimations de brisage (plus-value) et de familiers (kamas par XP), prix utilisé réglable. Tout est collecté en permanence. Conception: [docs/superpowers/specs/2026-11-12-client-redesign-design.md](superpowers/specs/2026-11-12-client-redesign-design.md). Pas de démarrage automatique avec Windows, plus de lien vers un site.
- **Remise à zéro:** `reset-data --yes` sauvegarde puis efface les données collectées (faite sur la base du propriétaire le 2026-11-13).
- **Noms d'objets pour les joueurs:** bouton « Télécharger les noms » dans Réglages (api.dofusdb.fr, une fois, à la demande), chargés dans la base.
- **Exécutable:** `.\dev.ps1 build` produit `dist\OpenDofusData.exe` (PyInstaller, sans console) et son SHA-256. Base, config et journal dans `%APPDATA%\OpenDofusData`.
- **Mises à jour, jamais automatiques:** vérification au démarrage de la dernière Release GitHub (désactivable), point de notification à côté de « Réglages », un clic télécharge, vérifie le SHA-256 et relance. Conception et limites: README, section « Mises à jour ».
- **Intégration continue:** `.github/workflows/ci.yml` (tests) et `release.yml` (publie l'exécutable et son empreinte sur la Release d'un tag `vX.Y.Z`). Non exécutés pour l'instant: ils le seront au premier push.

## À décider par le propriétaire

- **Licence:** décision du propriétaire: aucune, tous droits réservés (le code est public mais n'est pas libre). Les textes ne disent donc plus « open source ».
- **Première publication:** pousser le tag `v1.0.0` déclenche `release.yml`, qui publie une Release publique avec l'exécutable.
- **Signature de code** de l'exécutable: absente (coût d'un certificat). Windows SmartScreen avertit au premier lancement.
- **Installateur** (MSI, Inno Setup...): l'exécutable seul suffit pour l'instant.

## Catégories de données

Les trois catégories sont décodées et toujours collectées: HDV (validée en jeu), brisage et familiers (écrits à partir de captures d'un seul joueur et vérifiés contre ses captures d'écran; structure des messages: [docs/protocol-notes.md](protocol-notes.md)). Chacune a son compteur, ses lignes dans les Logs, sa vue et sa table dans `prices.db`.

À vérifier en jeu avec les nouvelles vues:
- Refaire l'action et comparer les vues Brisage et Familiers à l'écran.
- Recyclage: la capture réseau est abandonnée (décision du 2026-11-12). Les taux viennent du téléchargement DofusDB (colonne `recycling_nuggets` de `data/items.csv` et de la table `items`); les anciennes tables de recyclage sont supprimées des bases au démarrage.
- Brisage: concasser plusieurs exemplaires d'un même équipement (quantité > 1) et des objets de niveaux variés.
- Familiers: lancer l'outil avant la connexion, faire plusieurs améliorations (dont une montée de niveau) et comparer l'état avant et après.
- Brisage (coefficients) et familiers (expérience par ressource) se déduisent des enregistrements cumulés.

Le guide pour capturer de nouveaux cas: [docs/new-categories.md](new-categories.md).

## Synchronisation et serveur (plus tard)

- File d'envoi (colonne `synced_at`), identifiant d'enregistrement idempotent, reprises avec attente croissante.
- Contrat d'API, authentification, protection contre les données falsifiées.
- Serveur et SaaS d'affichage des prix.

## Pistes facultatives

- Caractéristiques (effets) des équipements dans l'HDV: non décodées.
- Recyclage: le taux n'est pas sur le réseau; il se calcule à partir de `recyclingNuggets` (voir docs/protocol-notes.md).
- Avertir quand le décodage ne voit plus rien après une mise à jour du jeu: pas de signal fiable aujourd'hui (rien n'est décodé tant que le joueur n'ouvre pas l'HDV), donc pas d'alerte pour éviter les fausses alarmes.
- `names-import` réduirait la table `servers` de la base locale de 27 à 15 lignes (CSV filtré aux serveurs classiques): non exécuté.
- Les noms de messages obfusqués (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque version du jeu: `messages.py` est à remettre à jour avec le mode `discover`.
