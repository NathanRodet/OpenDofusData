# Notes de protocole (Dofus 3, TCP 5555)

Établies à partir de deux captures du mode découverte (2026-11-10), croisées avec des captures d'écran du jeu pour trois objets: Ailes de Moskito (identifiant 307), Aile du Tofu Maléfique (376) et Âme capturée: Fourapin le Chaud (34095). Les noms courts de messages (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque version du jeu: ils sont isolés dans `src/opendofusdata/messages.py`.

## Format

Flux de messages Protobuf précédés de leur longueur, avec des enveloppes `type.ankama.com/<nom>`. Cela correspond à l'hypothèse de `framing.py`.

## Prix des lots (×1, ×10, ×100, ×1000)

- Requête client: `kcy`, champ 1 = identifiant de l'objet, champ 2 = 1.
- `kcy` existe aussi SANS le champ 2 (forme « désélection »). Le serveur répond alors par un `jzs` sans bloc de détail (champs 2 et 3 seulement): un accusé de réception sans prix, que le décodeur ignore à juste titre.
- Réponse serveur: `jzs` = `{1: {1: objet, 2: prix compactés, 3: ?, 4: ?}, 2: ?, 3: objet}`.
- Le champ 1.2 contient les prix en entiers variables compactés, dans l'ordre des lots ×1, ×10, ×100, ×1000. La valeur 0 signifie qu'il n'y a pas de lot de cette taille. Octets vérifiés contre l'écran:

| Objet | Octets (hex) | Valeurs | Écran |
|---|---|---|---|
| 307 | `ee05ec2dc986039fc21e` | 750, 5868, 49993, 499999 | 750, 5 868, 49 993, 499 999 |
| 376 | `9101d00ebd6500` | 145, 1872, 12989, 0 | 145, 1 872, 12 989 (pas de ×1000) |
| 34095 | `a98805000000` | 82985, 0, 0, 0 | 82 985 (×1 seulement) |
| 1022 | `01f306c42c00` | 1, 883, 5700, 0 | non vérifié |

- Champs non identifiés: 1.3 (897, 3695, 1336, 75860), 1.4 et 2 (104 ou 328). Ils ne sont pas nécessaires.

## Cours du marché

- Requête client: `iqp`, champ 1 = identifiant de l'objet.
- Réponse serveur: `ire`, avec deux listes de points répétés:
  - champ 1 = points des 24 heures (un par heure avec des ventes: 19 pour 307, 15 pour 376, 2 pour 34095);
  - champ 3 = points des 30 jours (30 points, un par jour).
- Chaque point: `{1: prix, 2: identifiant de l'objet, 3: horodatage ISO-8601 UTC en texte (ex. 2026-11-09T10:50:09.901212706Z, 9 chiffres de fraction), 4: quantité vendue}`.
- Les statistiques affichées se recalculent exactement à partir des points (vérifié sur les trois objets):
  - articles vendus = somme des quantités;
  - prix médian = médiane pondérée par les quantités;
  - prix moyen = somme(prix × quantité) / somme(quantités), tronqué à l'entier (568,7 s'affiche 568);
  - dernier achat = horodatage du dernier point des 24 heures (heure locale = UTC + 1 en novembre);
  - 30 jours: tous les points du champ 3;
  - 7 jours: aucun message dédié; fenêtre qui débute à minuit UTC de (date de capture − 7 jours), bornes incluses: `début = (capture − 7 jours)` tronqué à 00:00:00 UTC, on garde les points des 30 jours dont l'horodatage est `>= début`. Vérifié sur quatre objets: 307 → 521 / 486 / 15 998, 376 → 46 / 73 / 14 208, 1554 (Rune Ra Vi), 32526 (Filet multiplicateur de Volkorne, capturé le 2026-11-10T20:16:17Z → 5 989 / 5 788 / 724). L'ancienne règle (au plus 7 jours avant le dernier point) échouait sur 32526: elle écartait le point du 2026-11-03T16:23 UTC (21 vendus, prix 6 047) que le jeu garde, et donnait 5 989 / 5 781 / 703.
- « Dernière mise à jour »: aucun champ serveur trouvé; elle vaut l'heure de la requête. L'outil utilise l'heure de capture.
- Le « Prix moyen » de la liste (359 pour 307, 15 923 pour 34095) est la moyenne pondérée des 30 jours.

## Questions ouvertes (à vérifier en jeu)

- Fenêtre de 7 jours: la règle « minuit UTC de (date de capture − 7 jours) » est vérifiée sur cinq objets (307, 376, 1554, 32526, 32525). Le Filet multiplicateur de Dragodinde (id 32525, aucune vente depuis 2 jours) affiche 11 630 / 12 253 / 112, comme prédit.
- RÉSOLU: objet sans aucune offre (vérifié en jeu avec la Rune Pata Ré Pa, id 20624, fiche « Cet objet n'est pas en vente actuellement »): le décodage ne produit rien, 0 enregistrement. Décision du propriétaire: on n'enregistre pas de prix quand il n'y a pas d'offre; l'absence de relevé ne signifie pas prix 0, le dernier prix connu garde son horodatage d'origine.

## Limites

- Les identifiants d'objets des messages capturés (y compris le champ d'objet de la fenêtre de recyclage) sont les identifiants d'objets DofusDB: vérifié pour 307, 376, 34095, 33528, 33530, 8139 et 17134.
- Les messages ne contiennent pas les noms d'objets, seulement leurs identifiants.
- Le serveur de jeu (Dofus a plusieurs serveurs) n'est pas identifié dans ces messages: le nom du serveur est choisi par le joueur (voir le README, « Serveur de jeu »).
- Aucun identifiant de serveur n'existe dans les messages de connexion / handshake (vérifié sur une capture d'une connexion à Kourial): le serveur de jeu est choisi par le joueur, aucune détection à partir du trafic n'est possible. Le champ 5 de `itv` (valeurs 355 / 457) ressemble à une latence et n'est PAS un identifiant de serveur; les autres correspondances avec des identifiants de serveur dans les captures précédentes étaient des coïncidences dans des listes d'objets.

## Recyclage (décodé, trois captures du 2026-11-11)

Captures `captures/recyclage-*.jsonl` (structure seule), vérifiées contre l'écran: sept recyclages dont 0, 0, 1, 2 et 3 Pépites. Les noms courts des messages changent à chaque version du jeu (constantes dans `messages.py`, suiveur dans `recycling.py`).

- Ouvrir la fenêtre: client `itz` {1, 3}, serveur `itv` et `kbq`.
- Ajouter un objet: client `jys` {1 = identifiant d'instance (pile), 3 = quantité à ajouter}; le serveur répond `kch` {3.1.3 = quantité, 3.1.4 = **identifiant d'objet DofusDB**, 3.1.5 = identifiant d'instance, 3.4 = 63 constant}. Vérifié avec 417 (Boue du Boo), 15073 (Œil de Truchtine), 310 (Os de Chafer), 2278 (Tissu Invisible).
- Changer une quantité: le client envoie `jys` avec une quantité relative (18446744073709551615 = −1 en 64 bits, ou +95); le serveur répond `kdr`, **de même forme que `kch`, avec le NOUVEAU TOTAL** (100 → 99 → 98 → 97 → … puis +95 → 190).
- Retirer un objet: il n'y a pas de message dédié, il faut fermer la fenêtre: le client envoie `kiq` (vide, plusieurs fois) et le serveur `kbr`; la fenêtre oublie tous ses objets.
- Recycler: client `kba` {1 = compteur croissant (1, 2, 3, 4, 7 selon les captures; sens inconnu, non utilisé), 2 = 1}, puis serveur `kec`, **`kdd`** et des `irx`.
- Résultat: **`kdd` {3 = nombre de Pépites}**, le champ est ABSENT quand le résultat est 0 (vérifié: 0, 0, 1, 2, 3). Confirmé par `irx` {3.1 = nouvelle quantité, 3.3 = instance 4300333}: la pile de Pépites passe de 19489 à 19492 (+3) puis 19493 (+1). Les `irx` des piles recyclées donnent leur quantité restante (5987 = 5988 − 1...).
- Non présents sur le réseau (donc calculés par le client): les rendements par objet (0,33 / 1,47 / 0,07 / 0,41, 3,30 pour 1000 Os de Chafer...), la valeur estimée (somme des prix moyens × quantités: 47130 + 252180 + 45400 + 185080 = 529790) et la capacité 4/800. Le jeu n'envoie donc jamais le taux: il se déduit en cumulant de nombreux recyclages (objets recyclés → Pépites obtenues), ce que fait la catégorie.
- Ce qui reste à valider: l'identifiant d'objet de la Pépite (14635) n'apparaît pas dans ces messages (le résultat n'est qu'une quantité), ce qui suffit puisque le recyclage ne donne que des Pépites.

## Familiers, amélioration (une capture, hypothèses)

Capture `captures/familier-temoin.jsonl`: une amélioration validée (125 Os de Chafer et 2 Œil de Truchtine). L'aperçu des gains du jeu (+5 expérience, +8 niveaux...) n'est jamais envoyé: il est calculé par le client.

- Valider: client `irb` {2 = instance du familier, 3 = liste de {1 = quantité, 3 = instance de la pile}}; les objets ne sont désignés que par leur instance, jamais par leur identifiant d'objet.
- Réponse: `irx` des piles consommées (nouvelle quantité) et `iqy` (le familier mis à jour: 1.1.4 = 6716, 1.1.5 = instance du familier, effets dans 1.1.7).
- Manque: la correspondance instance → identifiant d'objet (l'inventaire envoyé à la connexion) et l'état du familier avant et après pour en déduire les gains. Voir [docs/new-categories.md](new-categories.md).

## Autres messages vus (hors périmètre)

`jnz`, `kne`, `knb`, `kpy`, `kjz`, `jns`, `irl` (grosse liste d'objets) sont très fréquents; non analysés.
