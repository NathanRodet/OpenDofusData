# OpenDofusData

OpenDofusData est un petit programme Windows qui **écoute passivement le trafic réseau de Dofus 3** pendant que tu joues et range ce qu'il comprend dans une base de données **sur ton ordinateur**. Il transforme ensuite ces données en tableaux pour t'aider à acheter, briser et nourrir tes familiers plus intelligemment.

> **Serveur en ligne: à venir.** Pour l'instant, tout reste sur ta machine et **rien n'est envoyé**. Un serveur en ligne qui permettra de synchroniser les prix entre joueurs arrivera plus tard; il ne transmettra que les mêmes données de jeu, jamais d'informations personnelles.

Version actuelle: **2.0.0** (affichée dans Réglages).

## Ce que l'outil fait pour toi

| Page | À quoi ça sert |
|---|---|
| **HDV** | Tous les objets dont tu as consulté la fiche à l'HDV: dernier prix, prix médian sur 24 h, nombre vendus, courbes sur 24 h / 7 jours / 30 jours, prix des lots de 1, 10, 100 et 1000, historique des relevés. |
| **Brisage** | La liste de tes brisages: pour chaque objet, son prix HDV le plus bas, son coefficient de brisage moyen et la plus-value moyenne (valeur des runes obtenues moins prix de l'objet). Un clic détaille la plus-value rune par rune en brisage classique, et en focus sur la stat la plus rentable. |
| **Craft** | Les crafts dont tous les prix sont connus, du plus rentable au moins rentable, avec le détail des ressources. |
| **Familiers** | Combien d'XP donne une ressource à un familier, et ce que coûte un point d'XP (trié du moins cher au plus cher). Tu peux ajouter toi-même l'XP observée pour x ressources, voir le « stop » de prix à 25 kamas par XP, et consulter l'onglet **Couverture**: combien de ressources ont un coefficient connu, et lesquelles manquent (filtrable par catégorie). |
| **Logs** | Ce qui est capté en direct, filtrable par type, période et nom. |
| **Réglages** | Serveur de jeu, emplacement de la base, noms d'objets, prix utilisé pour les estimations, mises à jour. |

Chaque page se filtre par période (dernière heure, 6 heures, aujourd'hui, 7 jours, 30 jours, tout ou personnalisé), se trie en cliquant sur les en-têtes et ne montre que le serveur choisi dans Réglages.

> Le brisage et les familiers sont encore en bêta: ils ont été validés sur les captures d'un seul joueur. Compare ce que tu vois avec l'écran du jeu.

## Installer

1. **Installe [Npcap](https://npcap.com)** (Windows 11). Il n'est pas fourni avec l'outil. Ne coche pas « Restrict Npcap driver's access to Administrators only », sinon lance OpenDofusData en administrateur. Le mode « WinPcap API-compatible » n'est pas nécessaire.
2. **Télécharge `OpenDofusData.exe`** depuis la page [Releases](https://github.com/NathanRodet/OpenDofusData/releases). Le fichier `OpenDofusData.exe.sha256` contient son empreinte si tu veux la vérifier (`Get-FileHash OpenDofusData.exe`).
3. **Double-clique sur `OpenDofusData.exe`**, de préférence **avant** de te connecter au jeu. Le programme n'est pas signé: si Windows affiche « Windows a protégé votre ordinateur », clique sur « Informations complémentaires » puis « Exécuter quand même ».
4. Dans **Réglages**, **choisis ton serveur de jeu** (le trafic ne permet pas de le deviner). La capture redémarre toute seule avec ce choix. Facultatif: « Télécharger les noms » pour voir les noms d'objets au lieu des numéros.

Aucune installation de Python n'est nécessaire.

## Utiliser

- Lance le programme **avant** de te connecter au jeu, puis joue normalement. Tu peux le laisser ouvert en arrière-plan; fermer la fenêtre arrête la capture. Il ne démarre pas tout seul avec Windows.
- **HDV:** seuls les objets dont tu ouvres la fiche sont enregistrés.
- **Familiers:** l'outil a besoin de l'inventaire envoyé à la connexion pour reconnaître les ressources. Si les Logs indiquent « reconnecte-toi au jeu », déconnecte-toi puis reconnecte-toi une fois l'outil lancé.
- **Brisage et effets des objets:** certaines estimations demandent des données de référence (effets, runes, recettes) à télécharger une fois depuis DofusDB; voir la [documentation développeur](docs/developpement.md).
- Le bas du menu à gauche montre l'état de la capture (active, arrêtée, ou une erreur claire comme « Npcap absent »), le serveur et le bouton « Arrêter » / « Relancer ».

## Où sont mes données

Tout est dans `%APPDATA%\OpenDofusData`: la base `prices.db`, la configuration `config.json` et le journal technique `opendofusdata.log`. Tu peux changer l'emplacement de la base dans Réglages.

## Mises à jour

Elles ne sont **jamais automatiques**. Au démarrage, le programme demande à GitHub s'il existe une version plus récente (une requête anonyme, désactivable dans Réglages). S'il y en a une, un point bleu apparaît à côté de « Réglages ». Un clic sur « Mettre à jour et relancer » télécharge la nouvelle version, vérifie son empreinte SHA-256 et relance le programme. Comme il n'est pas signé, ne mets à jour que depuis les Releases de ce dépôt.

## Confidentialité

- L'outil ne garde que des données de jeu: identifiants d'objets, prix, quantités, dates, et le nom du serveur que tu as choisi.
- Il **ne stocke ni n'envoie** jamais d'adresse IP, de compte, de nom de personnage ni de chat.
- **Rien ne quitte ta machine** dans cette version. Les seules connexions du programme sont la vérification des mises à jour (api.github.com, désactivable) et, seulement si tu cliques sur « Télécharger les noms », le téléchargement des noms depuis api.dofusdb.fr.
- Le code source est public pour que ce comportement puisse être vérifié.

## Limites connues

- Les messages du jeu changent à chaque mise à jour de Dofus: après une mise à jour du jeu, l'outil peut ne plus rien décoder jusqu'à une nouvelle version (voir la [documentation développeur](docs/developpement.md)).
- Seuls l'HDV, le brisage et les familiers sont décodés. Pas d'achats, de ventes ni de changements de prix.
- Un objet sans aucune offre à l'HDV n'est pas enregistré: l'absence de relevé ne veut pas dire prix à 0.
- Le serveur de jeu n'est pas détecté automatiquement: c'est toi qui le choisis.

## Pour aller plus loin

- [Documentation développeur](docs/developpement.md): installation depuis les sources, commandes, structure, publication d'une version.
- [Feuille de route](docs/roadmap.md) et [notes sur le protocole](docs/protocol-notes.md).

## Licence

Tous droits réservés. Le code est publié sur GitHub pour être consulté et vérifié, mais aucune licence n'autorise à le réutiliser, le modifier ni le redistribuer sans l'accord de l'auteur.
