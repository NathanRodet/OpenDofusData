# Feuille de route

État au 2026-11-11: la v1 (capture locale, décodage des prix de lots et des cours du marché, base SQLite, noms d'objets, choix du serveur, fenêtre joueur, exécutable et mises à jour) est terminée. Version du produit: 1.1.0 (tags `v1.0.0` publié, `v1.1.0` à publier: recyclage, brisage et familiers en bêta, correction de la reconnaissance des objets ramassés après la connexion).

## Validé en jeu

- Fenêtre des 7 jours: confirmée sur cinq objets, dont le Filet multiplicateur de Dragodinde (11 630 / 12 253 / 112). Les lignes 7 jours de la base locale ont été recalculées (sauvegarde `data/prices.backup-before-7d-recompute.db`).
- Capture en direct avec la fenêtre (objets réels visibles dans les logs), et exécutable packagé: il s'ouvre, capture, journalise dans `%APPDATA%\OpenDofusData` et se ferme proprement.

## Fait

- **Fenêtre du client:** `opendofusdata window`, fenêtre CustomTkinter à menu latéral (Accueil, Données, Logs, Réglages, À propos), thème sombre, redimensionnable. Conception: [docs/superpowers/specs/2026-11-11-player-client-ui-design.md](superpowers/specs/2026-11-11-player-client-ui-design.md). Pas de démarrage automatique avec Windows. L'adresse du site (`SAAS_URL`) est un espace réservé tant que le serveur n'existe pas.
- **Catégories désactivables:** `enabled_categories` dans `config.json`, filtre à l'entrée de la capture, interrupteurs dans la page Données, commande `opendofusdata categories`.
- **Noms d'objets pour les joueurs:** bouton « Télécharger les noms » dans Réglages (api.dofusdb.fr, une fois, à la demande), chargés dans la base.
- **Exécutable:** `.\dev.ps1 build` produit `dist\OpenDofusData.exe` (PyInstaller, sans console) et son SHA-256. Base, config et journal dans `%APPDATA%\OpenDofusData`.
- **Mises à jour, jamais automatiques:** vérification au démarrage de la dernière Release GitHub (désactivable), point de notification à côté de « À propos », un clic télécharge, vérifie le SHA-256 et relance. Conception et limites: README, section « Mises à jour ».
- **Intégration continue:** `.github/workflows/ci.yml` (tests) et `release.yml` (publie l'exécutable et son empreinte sur la Release d'un tag `vX.Y.Z`). Non exécutés pour l'instant: ils le seront au premier push.

## À décider par le propriétaire

- **Licence:** décision du propriétaire: aucune, tous droits réservés (le code est public mais n'est pas libre). Les textes ne disent donc plus « open source ».
- **Première publication:** pousser le tag `v1.0.0` déclenche `release.yml`, qui publie une Release publique avec l'exécutable.
- **Signature de code** de l'exécutable: absente (coût d'un certificat). Windows SmartScreen avertit au premier lancement.
- **Installateur** (MSI, Inno Setup...): l'exécutable seul suffit pour l'instant.

## Catégories de données

Les quatre catégories sont décodées: HDV (validée en jeu), et en **bêta, désactivées par défaut**, recyclage, brisage et familiers, écrits à partir de captures d'un seul joueur et vérifiés contre ses captures d'écran (structure des messages: [docs/protocol-notes.md](protocol-notes.md)). Chaque catégorie a son interrupteur, son compteur et ses lignes dans les Logs, et sa propre table dans `prices.db`.

À faire pour sortir de la bêta, avec les tests en jeu du propriétaire:
- Activer chaque catégorie dans la page Données, refaire l'action et comparer les Logs à l'écran.
- Recyclage: confirmer qu'un recyclage de plusieurs objets différents est complet.
- Brisage: concasser plusieurs exemplaires d'un même équipement (quantité > 1) et des objets de niveaux variés.
- Familiers: lancer l'outil avant la connexion, faire plusieurs améliorations (dont une montée de niveau) et comparer l'état avant et après.
- Estimer ensuite les rendements (Pépites par objet recyclé, coefficients de brisage, expérience par ressource) à partir des enregistrements cumulés: aucune de ces valeurs n'est envoyée par le jeu, le client les calcule.

Le guide pour capturer de nouveaux cas: [docs/new-categories.md](new-categories.md).

## Synchronisation et serveur (plus tard)

- File d'envoi (colonne `synced_at`), identifiant d'enregistrement idempotent, reprises avec attente croissante.
- Contrat d'API, authentification, protection contre les données falsifiées.
- Serveur et SaaS d'affichage des prix.

## Pistes facultatives

- Caractéristiques (effets) des équipements dans l'HDV: non décodées.
- Recyclage: confirmé, le taux est calculé côté client et absent du réseau; la catégorie enregistre donc les objets recyclés et les Pépites obtenues (voir docs/protocol-notes.md), le taux se déduira de nombreux recyclages.
- Avertir quand le décodage ne voit plus rien après une mise à jour du jeu: pas de signal fiable aujourd'hui (rien n'est décodé tant que le joueur n'ouvre pas l'HDV), donc pas d'alerte pour éviter les fausses alarmes.
- `names-import` réduirait la table `servers` de la base locale de 27 à 15 lignes (CSV filtré aux serveurs classiques): non exécuté.
- Les noms de messages obfusqués (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque version du jeu: `messages.py` est à remettre à jour avec le mode `discover`.
