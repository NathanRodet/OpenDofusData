# Feuille de route

État au 2026-11-11: la v1 (capture locale, décodage des prix de lots et des cours du marché, base SQLite, noms d'objets, choix du serveur) est terminée et fusionnée dans `main`. Version du produit: 1.0.0 (tag `v1.0.0`).

## Validé en jeu

- Fenêtre des 7 jours: confirmée sur cinq objets, dont le Filet multiplicateur de Dragodinde (11 630 / 12 253 / 112). Les lignes 7 jours de la base locale ont été recalculées (sauvegarde `data/prices.backup-before-7d-recompute.db`).

## Fenêtre du client (fait)

- `opendofusdata window`: fenêtre CustomTkinter à menu latéral (Accueil, Données, Logs, Réglages, À propos), thème sombre, redimensionnable. Conception: [docs/superpowers/specs/2026-11-11-player-client-ui-design.md](superpowers/specs/2026-11-11-player-client-ui-design.md). Choisie à la place d'une icône de zone de notification; pas de démarrage automatique avec Windows. L'adresse du site (`SAAS_URL` dans `app_links.py`) est un espace réservé tant que le serveur n'existe pas; le dépôt (`REPOSITORY_URL`) pointe vers https://github.com/NathanRodet/OpenDofusData.

## Packaging et distribution (en cours)

- Fait: `pyproject.toml` et commande `opendofusdata` (sans `.\dev.ps1`).
- Installateur Windows, démarrage automatique (volontairement absent pour l'instant); sans signature de code (projet open source).
- Mises à jour, jamais automatiques: quand une nouvelle version existe, un signe de notification apparaît dans la page À propos; un clic récupère la nouvelle version puis relance l'application. À décider avant de construire: où sont publiées les versions (par exemple les Releases du dépôt GitHub), le format d'installation, la vérification d'intégrité du téléchargement, et le fait que la vérification contacte un serveur (la v1 n'envoie rien).
- Choisir une licence (MIT, GPL, autre). Le dépôt https://github.com/NathanRodet/OpenDofusData est créé et sert de remote (`origin`).

## Catégories de données

L'outil collectera quatre catégories: données HDV (fait), données de recyclage des ressources, données de brisage, données d'expérience des pets. Les trois dernières demandent d'abord d'identifier les messages concernés avec `discover`, puis d'écrire un décodeur par catégorie.

## Catégories désactivables

- Fait: réglage `enabled_categories` dans `config.json` (défaut `["hdv"]`), filtre à l'entrée de la capture (`FilteringWriter`), interrupteurs dans la page Données de la fenêtre.
- Reste à faire avec chaque nouveau décodeur: l'enregistrer comme catégorie (`categories.py`, `available=True`) et filtrer aussi à l'envoi quand la synchronisation existera.
- Pas encore: commande `opendofusdata categories` en ligne de commande.

## Synchronisation et serveur (plus tard)

- File d'envoi (colonne `synced_at`), identifiant d'enregistrement idempotent, reprises avec attente croissante.
- Contrat d'API, authentification, protection contre les données falsifiées.
- Serveur et SaaS d'affichage des prix.

## Pistes facultatives

- Caractéristiques (effets) des équipements dans l'HDV: non décodées.
- Recyclage: à vérifier lors de l'analyse des messages. Un ancien constat indiquait que le taux de recyclage est calculé côté client et absent du réseau; la collecte vise donc ce que le trafic expose réellement.
- `names-import` réduirait la table `servers` de la base locale de 27 à 15 lignes (CSV filtré aux serveurs classiques): non exécuté.
- Plusieurs points mineurs différés sont listés dans `.superpowers/sdd/2026-11-09-hdv-price-capture-v1/progress.md` (local, non versionné).
- Les noms de messages obfusqués (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque version du jeu: `messages.py` est à remettre à jour avec le mode `discover`.
