# Notes de protocole (Dofus 3, TCP 5555)

Établies à partir de `captures/discovery.jsonl` (capture du 2026-11-10, objet « Ailes de Moskito », identifiant 307) croisée avec des captures d'écran du jeu. Les noms courts de messages changent à chaque version du jeu.

## Format confirmé

Le flux est bien une suite de messages Protobuf précédés de leur longueur, avec des enveloppes `type.ankama.com/<nom>`. Aucun écart avec l'hypothèse de `framing.py`.

## Cours du marché (écran « Cours du marché »)

- Requête client: `iqp`, champ 1 = identifiant de l'objet (307).
- Réponse serveur: `ire`. Chaque point répété a la forme `{1: prix, 2: identifiant de l'objet, 3: message de date (30 octets, non décodé), 4: quantité vendue}`.
  - Champ 1 répété (19 points pour 307): courbe des 24 heures. Vérifié sur l'écran: somme des quantités = 1 177 articles vendus, médiane pondérée = 584, moyenne pondérée = 568,7 (affichée 568), prix entre 499 et 643.
  - Champ 3 répété (30 points): courbe des 30 jours. Moyenne pondérée = 358,8 (affichée 359 dans la liste « Prix moyen »), 79 129 articles vendus.
  - Le champ 2 (7 jours) n'apparaît pas dans cette réponse. Hypothèse: l'onglet 7 jours est calculé côté client à partir des 30 jours.
- Dates affichées à l'écran (« Dernière mise à jour », « Dernier achat »): non localisées. Elles sont probablement dans le message de 30 octets (champ 3 de chaque point) ou dans un autre message.

## Prix des lots (×1, ×10, ×100, ×1000)

- Requête client: `kcy`, champ 1 = identifiant de l'objet, champ 2 = 1.
- Réponse serveur: `jzs` = `{1: {1: objet, 2: octets compactés (10 octets pour 307), 3: 897, 4: 104}, 2: 104, 3: objet}`.
- Hypothèse: le champ 1.2 contient les quatre prix de lots en entiers variables compactés (750, 5 868, 49 993, 499 999 occupent exactement 2 + 2 + 3 + 3 = 10 octets). Les champs 1.3 (897) et 1.4 / 2 (104) ne sont pas identifiés.
- À vérifier avec les octets réels de ce champ.

## Autres messages vus (hors périmètre)

`jnz`, `kne`, `knb`, `kpy`, `kjz`, `jns`, `irl` (grosse liste d'objets, inventaire ou liste HDV) sont très fréquents; non analysés.
