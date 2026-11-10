# Notes de protocole (Dofus 3, TCP 5555)

Établies à partir de deux captures du mode découverte (2026-11-10), croisées avec des captures d'écran du jeu pour trois objets: Ailes de Moskito (identifiant 307), Aile du Tofu Maléfique (376) et Âme capturée: Fourapin le Chaud (34095). Les noms courts de messages (`jzs`, `ire`, `kcy`, `iqp`) changent à chaque version du jeu: ils sont isolés dans `src/dofus_prices/messages.py`.

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
  - 7 jours: aucun message dédié; ce sont les points des 30 jours situés au plus 7 jours avant le dernier point (vérifié: 307 → 521 / 486 / 15 998, 376 → 46 / 73 / 14 208).
- « Dernière mise à jour »: aucun champ serveur trouvé; elle vaut l'heure de la requête. L'outil utilise l'heure de capture.
- Le « Prix moyen » de la liste (359 pour 307, 15 923 pour 34095) est la moyenne pondérée des 30 jours.

## Questions ouvertes (à vérifier en jeu)

- Ancre de la fenêtre de 7 jours: l'outil prend les points des 30 jours situés au plus 7 jours avant le DERNIER point des 30 jours. Cette ancre et l'heure de capture reproduisent toutes deux l'écran pour les objets 307 et 376 (échangés le jour de la capture). Pour un objet rarement échangé, la ligne 7j peut donc différer de l'onglet du jeu: comparer en jeu et, si le jeu n'affiche rien, ancrer sur `captured_at`. L'onglet 7 jours a aussi été vérifié en direct sur un objet échangé en continu (Rune Ra Vi : 1 935 / 1 938 / 243 717) et sur les captures hors ligne, qui ne permettent pas de départager l'ancre.
- RÉSOLU: objet sans aucune offre (vérifié en jeu avec la Rune Pata Ré Pa, id 20624, fiche « Cet objet n'est pas en vente actuellement »): le décodage ne produit rien, 0 enregistrement. Décision du propriétaire: on n'enregistre pas de prix quand il n'y a pas d'offre; l'absence de relevé ne signifie pas prix 0, le dernier prix connu garde son horodatage d'origine.

## Limites

- Les identifiants d'objets des messages capturés (y compris le champ d'objet de la fenêtre de recyclage) sont les identifiants d'objets DofusDB: vérifié pour 307, 376, 34095, 33528, 33530, 8139 et 17134.
- Les messages ne contiennent pas les noms d'objets, seulement leurs identifiants.
- Le serveur de jeu (Dofus a plusieurs serveurs) n'est pas identifié dans ces messages: l'outil prend le nom du serveur en option.
- Aucun identifiant de serveur n'existe dans les messages de connexion / handshake (vérifié sur une capture d'une connexion à Kourial): la détection se fait par l'adresse IP du serveur de jeu (Kourial = 99.81.217.174), apprise puis reconnue.
- Le serveur de jeu n'est pas encore identifié dans les messages capturés: le champ 5 de `itv` (valeurs 355 / 457) ressemble à une latence et n'est PAS un identifiant de serveur; les autres correspondances avec des identifiants de serveur dans les captures précédentes étaient des coïncidences dans des listes d'objets.

## Autres messages vus (hors périmètre)

`jnz`, `kne`, `knb`, `kpy`, `kjz`, `jns`, `irl` (grosse liste d'objets) sont très fréquents; non analysés.
