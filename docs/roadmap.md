# Feuille de route

État au 2026-11-11: la v1 (capture locale, décodage des prix de lots et des cours du marché, base SQLite, noms d'objets, choix du serveur) est terminée et fusionnée dans `main`.

## Validé en jeu

- Fenêtre des 7 jours: confirmée sur cinq objets, dont le Filet multiplicateur de Dragodinde (11 630 / 12 253 / 112). Les lignes 7 jours de la base locale ont été recalculées (sauvegarde `data/prices.backup-before-7d-recompute.db`).

## Packaging et distribution (non commencé)

- `pyproject.toml` et commande `dofus-prices` (sans `.\dev.ps1`).
- Installateur Windows, démarrage automatique, mises à jour; sans signature de code (projet open source).
- Choisir une licence (MIT, GPL, autre) et créer le dépôt distant; aucun remote n'est configuré.

## Synchronisation et serveur (plus tard)

- File d'envoi (colonne `synced_at`), identifiant d'enregistrement idempotent, reprises avec attente croissante.
- Contrat d'API, authentification, protection contre les données falsifiées.
- Serveur et SaaS d'affichage des prix.

## Pistes facultatives

- Caractéristiques (effets) des équipements dans l'HDV: non décodées.
- Taux de recyclage: hors périmètre (calculé côté client du jeu, absent du réseau).
- `names-import` réduirait la table `servers` de la base locale de 27 à 15 lignes (CSV filtré aux serveurs classiques): non exécuté.
- Plusieurs points mineurs différés sont listés dans `.superpowers/sdd/2026-11-09-hdv-price-capture-v1/progress.md` (local, non versionné).
- Les noms de messages obfusqués (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque version du jeu: `messages.py` est à remettre à jour avec le mode `discover`.

## Branche conservée

`feat/hdv-price-capture-v1` (ancienne branche de travail, déjà fusionnée) est gardée à ta demande initiale.
