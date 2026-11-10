# Capture des prix HDV Dofus: conception v1

## Intention

Le joueur veut garder une trace locale des prix de l'hôtel des ventes (HDV) de Dofus 3 pendant qu'il joue. Une première idée était l'OCR de l'écran; on a retenu la capture réseau passive, plus fiable, car Dofus 3.7 envoie du Protobuf en clair sur TCP 5555. Dans la v1 tout reste local: aucun envoi vers un serveur externe. Objectif global à plus long terme (précisé par le joueur): ce client récolte les prix, les stocke en SQLite, puis alimentera un serveur distant; la synchronisation et le serveur seront conçus plus tard.

## Objectifs

- Quand le joueur consulte un objet à l'HDV, enregistrer ses prix pour les lots ×1, ×10, ×100 et ×1000 (prix total du lot) dans une base SQLite locale.
- Enregistrer aussi les cours du marché affichés par l'écran de statistiques d'un objet: pour chaque période (24 h, 7 jours, 30 jours), les points de la courbe de prix, le prix médian, le prix moyen et le nombre d'articles vendus, plus la date de dernière mise à jour des données et la date du dernier achat. Chaque relevé stocke la date de mise à jour fournie par le serveur, en plus de la date de capture locale.
- Permettre de lister les prix, de voir l'historique d'un objet et d'exporter en CSV, en ligne de commande.
- Fournir un mode « découverte » qui journalise les noms de messages et la structure de leurs champs, pour valider le décodage sur du trafic réel.
- Résister aux défauts de reconstruction TCP connus: perte de paquet (resynchronisation), passage de 2³² sur le numéro de séquence, padding Ethernet (bornage par la longueur IP), purge des flux inactifs, lancement de l'outil en cours de connexion.

## Hors périmètre (v1)

- Achats, mises en vente, modifications de prix.
- Interface graphique et affichage en direct.
- Tout envoi réseau sortant vers un serveur distant (prévu plus tard, hors v1) et toute modification du trafic (capture strictement passive).
- Support de macOS ou Linux.

## Anti-objectifs

- Un outil qui « fonctionne » mais enregistre des prix faux (ex. prix du lot pris pour un prix unitaire) est un échec.
- Pas de paquets bruts écrits sur disque.
- Pas de code monolithique: les règles de CLAUDE.md s'appliquent (fonctions de 20 lignes maximum, modules de 200 lignes maximum).

## Contraintes

- Windows 11, Python 3.13, Npcap 1.90 installé au niveau du système (déjà présent), venv `.venv`, dépendances dans `requirements.txt` (`scapy`, `pytest`).
- Le jeu et l'outil tournent sur la même machine; l'outil doit être lancé avant la connexion au jeu, ou savoir se resynchroniser.
- Le builder ne peut pas lancer Dofus: tout est validé par des tests sur données synthétiques, puis par des captures réelles fournies par le joueur.
- Les numéros de champs Protobuf viennent d'Astrub Companion (licence MIT); les noms de messages courts (kcy, jzs, plus les anciens keh, kbt, jzn) changent à chaque version du jeu et devront être isolés dans un seul module de configuration.

## Décisions prises avec le joueur

- Interface de la v1: ligne de commande avec export CSV, sans affichage en direct.
- Découpage en couches: capture, reconstruction TCP, découpage des trames, décodeur Protobuf générique, décodage HDV, stockage SQLite, CLI. La logique pure ne dépend ni de Scapy ni de SQLite.
- Ordre de construction: reconstruction TCP, trames et décodeur générique, capture en mode découverte, décodage HDV, stockage et commandes.
- Le joueur lance le mode découverte à l'HDV et renvoie le log (1 à 3 allers-retours attendus) avant que le décodage HDV soit considéré comme validé.

## Point incertain: cours du marché

On suppose que les statistiques de l'écran « cours du marché » (courbes 24 h, 7 jours, 30 jours, médian, moyen, articles vendus, dates) transitent dans le trafic TCP 5555 comme les prix de lots. Ce n'est pas vérifié: le nom et les champs de ce message ne sont pas documentés par Astrub Companion. Ils seront identifiés avec le mode découverte, en ouvrant cet écran pour plusieurs objets et plusieurs périodes. Si ces données n'apparaissent pas dans le trafic, cet objectif sort de la v1 et reste à rediscuter (l'OCR de l'écran redevient alors une piste).

## Laissé au builder

- Choix de la bibliothèque de capture dans Scapy (sniff) et des noms exacts des modules, fonctions et tables.
- Schéma SQLite (au minimum: objet, serveur, date de relevé, taille de lot, prix; et pour les cours du marché: objet, période, points de courbe, médian, moyen, articles vendus, date de mise à jour serveur, date du dernier achat), sous réserve de conserver l'historique des relevés.
- Format du log de découverte et des commandes CLI (liste, historique, export CSV).
- Gestion des erreurs et journalisation via `logging`.

## Appels du rédacteur (à vérifier)

- Le schéma conserve l'historique complet des relevés et ne garde pas seulement le dernier prix.
- La capture filtre `tcp port 5555` et n'interprète que les enveloppes de messages Dofus, ignorant les autres services sur ce port.
- L'envoi vers la base se fait hors de la boucle de capture (file d'attente ou thread séparé), pour ne pas provoquer de perte de paquets.
