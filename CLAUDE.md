# OpenDofusData

Outil local (Python 3.13, Windows) qui capture le trafic réseau de Dofus (TCP 5555) via Npcap/Scapy, décode les messages utiles et les stocke dans une base SQLite locale. Catégories de données collectées: HDV, brisage, expérience des pets; tout est collecté en permanence, sans interrupteur (V2). Le recyclage n'est pas capturé: ses taux viennent de la colonne `recycling_nuggets` de `data/items.csv` (DofusDB). Objectif global: ce client récolte les données, les stocke en SQLite, puis alimentera à terme un serveur distant. Le serveur d'authentification par clés (`src/server/`, FastAPI, voir docs/developpement.md) et, côté client, la carte Synchronisation (clé et test de connexion) et l'onglet Administration existent: enregistrer une clé active l'envoi et la récupération des prix de lots de l'HDV, des brisages, des améliorations de familiers capturés et des saisies manuelles d'XP des familiers (le retirer les arrête, aucune case à cocher; seuls les favoris restent locaux), et les autres requêtes réseau sont la vérification des mises à jour, le téléchargement des données de référence depuis DofusDB (automatique tant qu'elles sont absentes, puis sur clic) et le test de connexion (sur clic); l'adresse du serveur de synchronisation se règle dans Réglages. Les statistiques de marché ne sont pas synchronisées. Aucune adresse de joueur n'est collectée, enregistrée ni transmise.

## Règles de code

- Fonctions courtes: 20 lignes maximum, une seule responsabilité.
- Fichiers segmentés par rôle (capture, reconstruction TCP, décodage, stockage), 200 lignes maximum par module.
- Noms explicites en anglais: `snake_case` pour fonctions et variables, `PascalCase` pour classes, `UPPER_CASE` pour constantes. Pas d'abréviations obscures ni de variables d'une lettre (sauf indices de boucle).
- Pas de nombres magiques: constantes nommées (ex. `DOFUS_PORT = 5555`).
- Annotations de type sur toutes les signatures; docstring courte sur les fonctions publiques.
- Un module par couche, dépendances dans un seul sens; la logique pure (décodage, reconstruction TCP) ne dépend ni de Scapy ni de SQLite pour être testable.
- Pas d'`except:` nu ni d'erreurs avalées silencieusement; logs via `logging`.
- Tests `pytest` sur des données synthétiques pour chaque module de logique.
- Dépendances listées dans `requirements.txt`, verrouillées avec leurs hashes dans `requirements.lock` (régénéré avec pip-compile, voir docs/developpement.md), installées dans le venv `.venv` (le serveur a son propre venv et ses propres verrous dans `src/server/`; jamais en global).
- Commandes de dev via `.\dev.ps1` (`setup`, `test`, `clean`, `build`); `.venv/`, `build/` et `dist/` sont à exclure du versionnement.
