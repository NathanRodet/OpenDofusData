# Feuille de route

État au 2026-11-11: la v1 (capture locale, décodage des prix de lots et des cours du marché, base SQLite, noms d'objets, choix du serveur, fenêtre joueur, exécutable et mises à jour) est terminée. Version du produit: 1.0.0 (tag `v1.0.0`, pas encore publié sur GitHub).

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

- **Licence** (MIT, GPL, autre): aucune n'est choisie alors que le dépôt est public.
- **Première publication:** pousser le tag `v1.0.0` déclenche `release.yml`, qui publie une Release publique avec l'exécutable.
- **Signature de code** de l'exécutable: absente (projet open source, coût d'un certificat). Windows SmartScreen avertit au premier lancement.
- **Installateur** (MSI, Inno Setup...): l'exécutable seul suffit pour l'instant.

## Catégories de données

L'outil collectera quatre catégories: données HDV (fait), données de recyclage des ressources, données de brisage, données d'expérience des pets. Les trois dernières demandent d'abord une capture en jeu pour identifier les messages: voir [docs/new-categories.md](new-categories.md). Ensuite, un décodeur par catégorie, enregistré dans `categories.py` (`available=True`) et filtré aussi à l'envoi quand la synchronisation existera.

## Synchronisation et serveur (plus tard)

- File d'envoi (colonne `synced_at`), identifiant d'enregistrement idempotent, reprises avec attente croissante.
- Contrat d'API, authentification, protection contre les données falsifiées.
- Serveur et SaaS d'affichage des prix.

## Pistes facultatives

- Caractéristiques (effets) des équipements dans l'HDV: non décodées.
- Recyclage: un ancien constat indiquait que le taux de recyclage est calculé côté client et absent du réseau; la collecte vise donc ce que le trafic expose réellement (à vérifier avec la capture).
- Avertir quand le décodage ne voit plus rien après une mise à jour du jeu: pas de signal fiable aujourd'hui (rien n'est décodé tant que le joueur n'ouvre pas l'HDV), donc pas d'alerte pour éviter les fausses alarmes.
- `names-import` réduirait la table `servers` de la base locale de 27 à 15 lignes (CSV filtré aux serveurs classiques): non exécuté.
- Les noms de messages obfusqués (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque version du jeu: `messages.py` est à remettre à jour avec le mode `discover`.
