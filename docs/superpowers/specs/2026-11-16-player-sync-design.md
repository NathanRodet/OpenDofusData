# Synchronisation des prix entre joueurs (conception)

Date: 2026-11-16. Statut: approuvée par le propriétaire, implémentée sur la branche `player-sync` (voir le plan pour les écarts).

## But

Les joueurs envoient au serveur les prix de l'HDV qu'ils observent et récupèrent ceux des autres, pour que chaque base locale contienne ce que tout le groupe a vu. Le serveur de clés existant (`src/server/`, clés signées, révocation) sert de porte d'entrée: seul un détenteur de clé non révoquée envoie ou reçoit.

## Objectifs

- Envoi automatique, en arrière-plan, des prix de lots de l'HDV (`lot_prices`), sans doublon même après une coupure.
- Récupération des relevés des autres joueurs, insérés dans la base locale sans jamais être renvoyés.
- Révocation d'une clé avec ou sans suppression de ses relevés du serveur (au choix de l'administrateur), sans jamais perdre ceux des autres joueurs.
- Base du serveur bornée (rétention de 7 jours, qui correspond à la fenêtre de 7 jours de l'application).
- Aucune adresse IP, aucun compte, aucun pseudo de personnage collecté ni conservé (règle du projet). Les relevés échangés portent le code de 11 caractères de la clé émettrice (décision du propriétaire): il permet de savoir d'où vient une donnée et de purger ou non les relevés d'une clé révoquée.

## Hors périmètre

- Statistiques de marché (`market_stats`), brisage et familiers: même mécanisme, mais dans un second temps.
- Protection contre les données falsifiées par la médiane entre contributeurs: reportée par le propriétaire. La seule protection est la révocation avec purge des relevés de la clé.
- Site d'affichage, comptes, plusieurs administrateurs, rotation du secret.

## Contraintes

- Règles de `CLAUDE.md` (fonctions de 20 lignes, modules de 200 lignes, annotations, pas de nombres magiques, tests sur données synthétiques, venv et dépendances verrouillées).
- Toute route du serveur est déclarée dans `ALLOWED_ROUTES`.
- Schémas Pydantic stricts (pas de champ en trop), corps limité à 1 Mio, 2000 relevés par lot au plus.
- Le client reste hors ligne par défaut: rien ne part sans réglage explicite du joueur (voir Client).
- Aucun texte avec tiret typographique long ni point médian (`tests/test_text_style.py`).

## Approches étudiées

- **A. Journal de relevés avec rétention (choisie).** Le serveur garde chaque relevé reçu, supprimé après 7 jours (choix du propriétaire). Courbes communes sur 7 jours, révocation sans perte, renvois sans danger. Coût: un peu plus de code et une base de l'ordre de 4 à 16 Mo pour 5 à 10 joueurs (estimation à 200 octets par ligne et 4 lignes par objet consulté, aucune mesure réelle: la base locale du propriétaire est vide). Les courbes de 24 heures et 30 jours viennent des messages du jeu (`market_stats`) et ne dépendent pas de cette rétention.
- **B. État courant seulement.** Une ligne par (serveur, objet, lot), la plus récente gagne. Base minuscule, mais pas d'historique commun et la révocation fait perdre aussi les prix honnêtes remplacés.
- **C. Hybride.** Journal sur le serveur, mais le client ne récupère que le dernier prix par clé: plus de code pour un gain faible.

Le propriétaire a retenu A avec purge par ancienneté.

## Conception

### Relevé de prix de lot

Champs: `server` (nom, mêmes règles que `ServerName`), `item_id` (1 à 10 000 000), `lot_size` (1, 10, 100 ou 1000), `price` (entier de 1 à 1 000 000 000 000, appel de la borne: à resserrer avec de vraies données), `observed_at` (UTC, dans la fenêtre acceptée par `ObservationTime`). Le prix est le prix total du lot, jamais un prix unitaire (comme `LotPrice`).

Clé naturelle d'un relevé côté serveur: (clé émettrice, serveur, objet, lot, `observed_at`), unique. Un relevé déjà reçu est compté en doublon, sans erreur.

### Serveur

- **`POST /readings`** (clé utilisateur): lot de 1 à 2000 relevés. Réponse `{"accepted": n, "duplicates": m}`. Chaque relevé garde l'identifiant (11 caractères) de la clé qui l'a envoyé.
- **`GET /readings?since=N&limit=L`** (clé utilisateur): relevés d'ordre supérieur à N, par ordre d'arrivée, `limit` de 1 à 2000. Réponse `{"readings": [...], "next": N2}`; chaque relevé porte `seq`, `key_id` (l'identifiant de la clé émettrice, décision du propriétaire), `server`, `item_id`, `lot_size`, `price`, `observed_at`. Les relevés de la clé qui demande ne lui sont pas renvoyés.
- **`GET /readings/latest?after=K&limit=L`** (clé utilisateur): premier lancement d'un joueur. Parcourt, par pages, le dernier relevé de chaque clé naturelle (serveur, objet, lot). La réponse donne aussi `as_of` (numéro d'ordre au début du parcours) et `done`; le client enchaîne ensuite avec `GET /readings?since=as_of`.
- **Chaînes de requête:** le garde-fou de format n'accepte, pour ces deux routes `GET`, que les paramètres déclarés (`since`, `limit`, `after`), chacun une seule fois, en entiers décimaux de 1 à 12 chiffres, sans encodage en pourcentage. Tout autre cas reste refusé en `400`. Un `GET` avec corps est refusé.
- **Purge par ancienneté:** les relevés dont `observed_at` a plus de 7 jours sont supprimés une fois par jour.
- **Révocation au choix:** `POST /admin/revoke` accepte `{"key_id": "...", "purge": true|false}` (`false` par défaut). La clé est révoquée d'abord; si `purge` est vrai, ses relevés sont ensuite supprimés (deux étapes ordonnées, rejouables). Sans purge, ses relevés restent servis jusqu'à la fin de la rétention.
- **Identité de la clé:** après vérification de la signature, l'identifiant de la clé est mis à disposition des routes (extension de la portée ASGI). Aucune adresse n'est lue. Le code de 11 caractères est un pseudonyme: il apparaît dans les relevés renvoyés aux autres joueurs, jamais la clé complète ni le pseudo choisi par l'administrateur.
- Stockage: la base SQLite existante (`keys.db`) ou une seconde, au choix du constructeur. Index: clé naturelle unique, clé émettrice (purge), date d'observation (rétention).

### Client

- **Réglages (carte Synchronisation):** décision du propriétaire du 2026-11-16, qui remplace les deux cases prévues à l'origine: pas de case à cocher, enregistrer une clé (avec une adresse de serveur) active l'envoi et la récupération, la retirer les arrête.
- **Base locale:** `lot_prices` reçoit `origin` (`local` ou `remote`), `synced_at` (vide tant que non envoyé) et `source_key_id` (l'identifiant de la clé émettrice d'une ligne reçue); migration sans perte des bases existantes (lignes existantes: `local`, non envoyées). Les vues de prix prennent le relevé le plus récent, quelle que soit l'origine.
- **Envoi:** un fil d'arrière-plan prend les lignes `local` non envoyées par lots de 2000, filtre un prix identique au dernier envoyé pour la même clé naturelle depuis moins d'une heure, envoie, puis renseigne `synced_at` seulement après la réponse `200`. Échec réseau: nouvelle tentative avec attente croissante bornée. `401`: arrêt et message clair, pas de nouvelle tentative.
- **Récupération:** au premier lancement `GET /readings/latest` puis `GET /readings`, ensuite seulement `GET /readings` depuis le dernier numéro mémorisé (dans la base locale). Les lignes reçues sont insérées avec `origin = remote` et `synced_at` renseigné, sans doublon.
- **Requêtes réseau:** HTTPS seulement via `https_json` (pas de redirection, délais et tailles bornés); aucun secret ni relevé dans les journaux.
- **Purge locale optionnelle (demande du propriétaire):** une case (décochée par défaut, au lancement) et un bouton dans Réglages suppriment de la base locale les relevés de prix et de statistiques de plus de 7 jours, en gardant toujours le plus récent de chaque clé; favoris, observations manuelles, noms, serveurs, brisages, familiers et état de synchro ne sont jamais touchés.
- **Documentation:** README (bannière et section Privacy), `docs/developpement.md`, feuille de route.

## Reste au constructeur

- Nom et schéma exacts des tables du serveur, et choix d'une base ou de deux.
- Forme de la tâche quotidienne de purge (au démarrage et par minuterie dans l'application, ou commande appelée par `cron`).
- Bornes de prix à resserrer, valeur d'attente maximale des reprises, taille des pages.

## Risques connus

- Un joueur qui falsifie ses prix fausse les valeurs affichées jusqu'à ce que sa clé soit révoquée (pas de médiane).
- Le volume réel est inconnu: à mesurer après quelques jours d'usage, puis ajuster la rétention.
