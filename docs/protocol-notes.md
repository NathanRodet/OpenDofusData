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
- **Le coefficient affiché (colonne « Personnage ») n'est pas sur le réseau, mais il se calcule:** chaque objet a un champ `recyclingNuggets` dans l'API publique de DofusDB (Os de Chafer 0,005495; Boue du Boo 0,011594; Tissu Invisible 0,068236; Œil de Truchtine 0,24435), et le jeu affiche **quantité × `recyclingNuggets` × 0,6**. Vérifié sur toutes les valeurs des captures: Os ×100 = 0,330 (affiché 0,33), ×1000 = 3,297 (3,30), ×190 = 0,626 (0,63), ×10 = 0,033 (0,03); Boue ×10 = 0,070; Tissu ×10 = 0,409 (0,41); Œil ×10 = 1,466 (1,47). Le facteur 0,6 est la **part du joueur**: depuis la mise à jour 3.3 (22/09/2025), le recyclage se fait à un prisme neutre du temple des alliances avec un taux fixe de **60 % pour le joueur et 40 % pour le prisme** (source: dofuspourlesnoobs.com/mise-a-jour-303.html, site communautaire; le devblog officiel n'est pas accessible automatiquement). Il ne dépend donc pas du personnage; les anciens recycleurs « équitable » (50/50), « collectiviste » (30 %) et « Koko » (10 %) appartiennent à l'ancien système et ne sont plus utilisés. Les autres valeurs du client restent absentes du réseau: la valeur estimée (somme des prix moyens × quantités: 47130 + 252180 + 45400 + 185080 = 529790) et la capacité 4/800. Les Pépites réellement obtenues (`kdd`) sont tirées au sort autour de ce coefficient: 0, 0 et 3 pour 0,003 / 0,033 / 3,297 attendues.
- Ce qui reste à valider: l'identifiant d'objet de la Pépite (14635) n'apparaît pas dans ces messages (le résultat n'est qu'une quantité), ce qui suffit puisque le recyclage ne donne que des Pépites.

## Familiers, amélioration (décodé, deux captures du 2026-11-11)

Captures `captures/familier-temoin.jsonl` et `captures/session-complete.jsonl` (cette dernière démarrée avant la connexion, avec `--max-fields 100000`). Constantes dans `messages.py`, suiveur dans `pets.py`.

- **Inventaire à la connexion:** serveur `irl`, champ 2 répété {1 = objet, 4 = conteneur}; objet {3 = quantité, 4 = **identifiant d'objet DofusDB**, 5 = **identifiant d'instance**, 7 = effets répétés}. 402 objets dans la capture. **L'identifiant d'instance change à chaque connexion** (l'Os de Chafer était 4854825, puis 2668079): la correspondance instance → objet ne se lit que dans l'inventaire de la même connexion, donc l'outil doit être lancé AVANT de se connecter au jeu.
- **Objets ajoutés après la connexion** (butin, objets fabriqués, runes): serveur `iqx`, de même forme qu'une entrée de l'inventaire (un objet par message: 3 = quantité, 4 = identifiant d'objet, 5 = instance, 7 = effets). Sans lui, une ressource ramassée après la connexion était inconnue et l'amélioration ignorée (constaté en jeu le 2026-11-12: seule la ressource présente à la connexion avait été enregistrée; les runes d'un brisage arrivent par `iqx`).
- **Valider une amélioration:** client `irb` {2 = instance du familier, 3 = liste répétée de {1 = quantité, 3 = instance de la pile}}. Les ressources ne sont désignées que par leur instance (2668079 = Os de Chafer dans l'inventaire de la même session).
- **Réponse:** serveur `irx` {3.1 = quantité restante, 3.3 = instance} pour chaque pile consommée (4787 − 100...), et `iqy` {1 = {1 = le familier mis à jour, 4 = conteneur}}.
- **Effets d'un familier** (champ 7 de l'objet, un message par effet): identifiant d'effet au champ 10. **176 = prospection** (valeur au champ 5). **2821 = niveau** (détail au champ 9: 9.4 = niveau actuel). **2819 = expérience** (9.4 = expérience actuelle, 9.2 = maximum du niveau). Vérifié: avant 257 → après 262, soit +5, exactement l'aperçu « EXPÉRIENCE +5 » du jeu; et dans la première capture, 31 → 32 (« +1 NIVEAU ») et prospection 45 → 46 (« +1 Prospection »).
- **L'expérience est cumulative:** elle ne repart pas de zéro à la montée de niveau. Exemple enregistré en jeu (800 Os de Chafer): niveau 33 → 34, expérience 286 → 329 (+43, comme l'aperçu) et maximum du niveau 319 → 356. Le gain d'expérience est donc toujours « après − avant ».
- **Non présents sur le réseau** (donc calculés par le client): l'aperçu des gains avant validation (+5, +335, +9 prospection...). Le gain réel se déduit de l'état du familier avant (inventaire ou mise à jour précédente) et après (`iqy`).
- **Limites:** sans l'inventaire de la connexion (outil lancé après la connexion), les ressources ne peuvent pas être attribuées à un objet et l'amélioration n'est pas enregistrée.

## Brisage, concasseur (décodé, une capture du 2026-11-11)

Capture `captures/brisage-1.jsonl`: trois concassages (1 Lisseur; 4 Volkornes; 2 Volkornes), vérifiés contre l'écran. Suiveur dans `breaking.py`, fenêtre partagée avec le recyclage dans `crafting_window.py`.

- **La fenêtre du Concasseur utilise les mêmes messages que celle du recyclage:** ouverture `itz` / `itv`, ajout client `jys` puis serveur `kch` (identifiant d'objet, quantité, instance), changement de quantité `kdr` (nouveau total), fermeture client `kiq`.
- **Briser:** client `jxy` {1 = compteur croissant, 3 = 1} puis serveur `kec`, puis le résultat `kag`.
- **Résultat `kag`:** champ 1 répété, un par objet détruit: {1 = **coefficient**, 2 = quasi identique, 3 = instance de l'objet détruit, 4 = runes répétées {1 = quantité, 2 = identifiant d'objet de la rune}}. Les champs 1 et 2 sont des flottants 32 bits: 1056964608 = 0,5 (50 %), 1057528607 = 0,53362 (le « 53 % » du Lisseur); le champ 2 diffère à peine (0,533616), seul le champ 1 est gardé. Un objet sans rune (le Lisseur) n'a pas de champ 4.
- **Vérifié:** Lisseur (942): 53 %, aucune rune. Volkorne Orchidée (33199): 50 %, Rune Ga Pa (1557) ×1 et Rune Ine (1522) ×38. Volkorne Ébène (33166): 50 %, Rune Age (1524) ×38 puis ×39. Volkorne Pourpre (33202): 50 %, Ga Pa ×1 et Rune Fo (1519) ×38. Tout correspond aux captures d'écran « Résultat du concassage ».
- **Non présents sur le réseau:** les valeurs estimées des objets détruits et des runes (162, 62949, 87606...).
- **Partage avec le recyclage:** les ajouts d'objets sont les mêmes messages; les deux suiveurs se vident mutuellement au résultat de l'autre (`kdd` / `kag`) pour qu'un objet du Concasseur ne se retrouve pas dans un recyclage.
- **Trois exemplaires identiques** (capture `brisage-2`, 3 Sandales du Piou Jaune, objet 8228): le jeu les liste comme trois objets distincts (trois instances, quantité 1 chacun, « 3/50 objets distincts »); résultat: coefficients 0,35525 / 0,35515 / 0,35505 (affichés « 36 % » pour les trois, arrondi au plus proche) et 2, 2, 1 Rune Age (1524), conformes à l'écran. Le coefficient baisse d'environ 0,0001 d'un objet au suivant dans le même concassage.
- **Six objets mélangés** (capture `brisage-3`, dont un lot empilé de 2 Sandales du Piou Jaune): coefficients 0,43649 / 0,26309 / 0,97543 / 0,15774 / 0,15771 / 0,35488, affichés 44 / 26 / 98 / 16 / 16 / 35 %: **l'affichage est l'arrondi à l'entier de 100 × le champ 1**. Le lot empilé arrive en `kch` (quantité 1) puis `kdr` (quantité 2) et n'a qu'UN coefficient et UN résultat pour les deux exemplaires (2 Rune Age). Le champ 2 est identique au champ 1 sauf pour le lot (0,35498 contre 0,35488). Runes vérifiées: Pod ×18, Ine ×4, Fo ×6, Vi ×2, Pui ×2...
- **À valider:** un lot empilé de plus de 2 exemplaires, et la raison de l'écart entre les champs 1 et 2, et si le champ 2 diffère de plus d'un millionième du champ 1 dans d'autres cas.

## Autres messages vus (hors périmètre)

`jnz`, `kne`, `knb`, `kpy`, `kjz`, `jns`, `irl` (grosse liste d'objets) sont très fréquents; non analysés.
