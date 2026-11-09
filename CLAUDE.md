# OpenDofusData

Outil local (Python 3.13, Windows) qui capture le trafic réseau de Dofus (TCP 5555) via Npcap/Scapy, décode les messages de l'HDV et stocke les prix dans une base SQLite locale. Aucun envoi vers un serveur externe.

## Règles de code

- Fonctions courtes: 20 lignes maximum, une seule responsabilité.
- Fichiers segmentés par rôle (capture, reconstruction TCP, décodage, stockage), 200 lignes maximum par module.
- Noms explicites en anglais: `snake_case` pour fonctions et variables, `PascalCase` pour classes, `UPPER_CASE` pour constantes. Pas d'abréviations obscures ni de variables d'une lettre (sauf indices de boucle).
- Pas de nombres magiques: constantes nommées (ex. `DOFUS_PORT = 5555`).
- Annotations de type sur toutes les signatures; docstring courte sur les fonctions publiques.
- Un module par couche, dépendances dans un seul sens; la logique pure (décodage, reconstruction TCP) ne dépend ni de Scapy ni de SQLite pour être testable.
- Pas d'`except:` nu ni d'erreurs avalées silencieusement; logs via `logging`.
- Tests `pytest` sur des données synthétiques pour chaque module de logique.
- Dépendances listées dans `requirements.txt`, installées dans le venv `.venv` (jamais en global).
- Commandes de dev via `.\dev.ps1` (`setup`, `test`, `clean`); `.venv/` est à exclure du versionnement.
