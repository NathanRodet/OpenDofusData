# Feuille de route

État au 2026-11-16: la V2 (refonte de la fenêtre) est publiée. Version du produit: 2.2.0 (tags `v1.0.0` et `v1.1.0` existants; `v2.0.0` et `v2.1.0` publiés le 2026-11-15; `v2.2.0` préparée, pas encore publiée). La 2.2.0 ajoute la synchronisation des prix de lots entre joueurs (envoi et récupération facultatifs, serveur de clés), la purge locale optionnelle, un seul bouton « Télécharger les données de référence » (noms, serveurs, recettes, effets), les pages Réglages et Administration refaites en sections et, dans Craft, les favoris et l'affichage des crafts incomplets. La 2.1.0 ajoutait le menu déroulant de période, les favoris et l'onglet Couverture des Familiers, le détail des runes obtenues en vrai, et le verrouillage des dépendances.

## Validé en jeu

- Fenêtre des 7 jours: confirmée sur cinq objets, dont le Filet multiplicateur de Dragodinde (11 630 / 12 253 / 112). Les lignes 7 jours de la base locale ont été recalculées (sauvegarde `data/prices.backup-before-7d-recompute.db`).
- Capture en direct avec la fenêtre (objets réels visibles dans les logs), et exécutable packagé: il s'ouvre, capture, journalise dans `%APPDATA%\OpenDofusData` et se ferme proprement.

## Fait

- **Fenêtre du client (V2):** `opendofusdata window`, fenêtre CustomTkinter pleine taille et responsive, menu HDV / Brisage / Familiers / Logs / Réglages, tableaux triables, filtres par période, détails avec courbes datées, estimations de brisage (plus-value) et de familiers (kamas par XP), prix utilisé réglable. Tout est collecté en permanence. Conception:. Pas de démarrage automatique avec Windows, plus de lien vers un site.
- **Remise à zéro:** `reset-data --yes` sauvegarde puis efface les données collectées (faite sur la base du propriétaire le 2026-11-13).
- **Noms d'objets pour les joueurs:** bouton « Télécharger les données de référence » dans Réglages (api.dofusdb.fr, une fois, à la demande): noms et serveurs chargés dans la base, recettes et effets écrits en CSV pour les pages Craft et Brisage.
- **Exécutable:** `.\dev.ps1 build` produit `dist\OpenDofusData.exe` (PyInstaller, sans console) et son SHA-256. Base, config et journal dans `%APPDATA%\OpenDofusData`.
- **Mises à jour, jamais automatiques:** vérification au démarrage de la dernière Release GitHub (désactivable), point de notification à côté de « Réglages », un clic télécharge, vérifie le SHA-256 et relance. Conception et limites: README, section « Mises à jour ».
- **Intégration continue:** `.github/workflows/ci.yml` (tests) et `release.yml` (publie l'exécutable et son empreinte sur la Release d'un tag `vX.Y.Z`). Non exécutés pour l'instant: ils le seront au premier push.

## À décider par le propriétaire

- **Licence:** décision du propriétaire: aucune, tous droits réservés (le code est public mais n'est pas libre). Les textes ne disent donc plus « open source ».
- **Première publication:** pousser le tag `v1.0.0` déclenche `release.yml`, qui publie une Release publique avec l'exécutable.
- **Signature de code** de l'exécutable: absente (coût d'un certificat). Windows SmartScreen avertit au premier lancement.
- **Installateur** (MSI, Inno Setup...): l'exécutable seul suffit pour l'instant.

## Catégories de données

Les trois catégories sont décodées et toujours collectées: HDV (validée en jeu), brisage et familiers (écrits à partir de captures d'un seul joueur et vérifiés contre ses captures d'écran; structure des messages: [protocol-notes.md](protocol-notes.md)). Chacune a son compteur, ses lignes dans les Logs, sa vue et sa table dans `prices.db`.

À vérifier en jeu avec les nouvelles vues:
- Refaire l'action et comparer les vues Brisage et Familiers à l'écran.
- Recyclage: la capture réseau est abandonnée (décision du 2026-11-12). Les taux viennent du téléchargement DofusDB (colonne `recycling_nuggets` de `data/items.csv` et de la table `items`); les anciennes tables de recyclage sont supprimées des bases au démarrage.
- Brisage: concasser plusieurs exemplaires d'un même équipement (quantité > 1) et des objets de niveaux variés.
- Familiers: lancer l'outil avant la connexion, faire plusieurs améliorations (dont une montée de niveau) et comparer l'état avant et après.
- Brisage (coefficients) et familiers (expérience par ressource) se déduisent des enregistrements cumulés.

Le guide pour capturer de nouveaux cas: [new-categories.md](new-categories.md).

## Synchronisation et serveur

Fait (branche `player-sync`, pas encore publié): serveur d'authentification par clés signées dans `src/server/` (révocation avec ou sans suppression des relevés de la clé, limites de requête, schémas stricts), synchronisation des prix de lots de l'HDV dans les deux sens (actifs dès qu'une clé est enregistrée, journal de 14 jours côté serveur, identifiant de la clé émettrice gardé avec chaque relevé), carte Synchronisation des Réglages, purge locale optionnelle des relevés de plus de 14 jours et onglet Administration. Détails dans [developpement.md](developpement.md).

Reste à faire:
- Synchroniser aussi les statistiques de marché, le brisage et les familiers (même mécanisme, un réglage par catégorie).
- Propagation de la purge d'une clé aux clients (le serveur publierait les clés purgées, les clients effaceraient les lignes dont `source_key_id` correspond): volontairement hors périmètre pour l'instant.
- Protection contre les données falsifiées (médiane entre contributeurs), reportée par le propriétaire, puis SaaS d'affichage des prix.

## Pistes facultatives

- Caractéristiques (effets) des équipements dans l'HDV: non décodées.
- Recyclage: le taux n'est pas sur le réseau; il se calcule à partir de `recyclingNuggets` (voir [protocol-notes.md](protocol-notes.md)).
- Avertir quand le décodage ne voit plus rien après une mise à jour du jeu: pas de signal fiable aujourd'hui (rien n'est décodé tant que le joueur n'ouvre pas l'HDV), donc pas d'alerte pour éviter les fausses alarmes.
- `names-import` réduirait la table `servers` de la base locale de 27 à 15 lignes (CSV filtré aux serveurs classiques): non exécuté.
- Les noms de messages obfusqués (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque version du jeu: `messages.py` est à remettre à jour avec le mode `discover`.
