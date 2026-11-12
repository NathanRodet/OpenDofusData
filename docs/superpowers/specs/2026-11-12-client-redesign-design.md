# Refonte du client joueur: tableaux de données, tout collecté, base locale

Date: 2026-11-12. Auteur du besoin: le propriétaire du projet. Maquette de référence (ouvrable dans un navigateur, données d'exemple): [2026-11-12-client-redesign-mockup.html](2026-11-12-client-redesign-mockup.html).

## Intention

Aujourd'hui le client est une petite fenêtre (colonne centrée de 480 px) avec des compteurs, des interrupteurs par catégorie et un flux de logs. Le propriétaire veut en faire un vrai **outil de consultation de ses données**: une fenêtre pleine taille, responsive, où l'on parcourt sous forme de tableaux, avec filtres, tout ce que le client a récolté dans la base SQLite locale.

Le client **récolte tout, en permanence**: expérience de familier, tous les prix HDV trouvables pour un objet, et les taux de brisage, chacun avec ses dates. Il n'y a plus de site web: le client lit sa propre base locale. Plus tard (hors périmètre de cette refonte) une synchronisation enverra ces données à un serveur distant.

Réussite: le joueur ouvre la fenêtre et voit, sans rien régler, ses données récentes dans trois tableaux (HDV, Brisage, Familiers) avec recherche, filtre par durée et courbes datées; la vue Familiers lui dit quelle ressource donne le plus d'XP pour le moins de kamas.

## Objectifs

- Fenêtre redimensionnable, le contenu occupe toute la largeur (pas de colonne centrée), thème sombre unique.
- Cinq entrées de menu: **HDV, Brisage, Familiers, Logs, Réglages**.
- Trois vues de données en tableau avec recherche, boutons de durée et tri; une fiche de détail avec courbe datée pour l'objet ou la ressource sélectionné.
- Vue Familiers: pour chaque ressource, prix d'1 ressource, XP pour 1 ressource, kamas par XP (colonne de tri, meilleur en premier) et coût pour monter un familier.
- Tout est collecté, toujours: plus aucun interrupteur de catégorie.

## Hors périmètre et anti-objectifs

- Pas de synchronisation, de serveur distant, de compte, de site web, ni de bouton « Voir les prix en ligne ». La refonte n'envoie rien à l'extérieur (la seule connexion reste le téléchargement des noms DofusDB et la vérification de mise à jour, inchangés).
- **Pas d'export CSV** dans l'interface (demande explicite).
- Pas de nouveaux décodeurs ni de changement du décodage réseau; pas de collecte du recyclage (retirée le 2026-11-12; seule la colonne `recycling_nuggets` des noms reste).
- Pas de thème clair, pas de démarrage automatique avec Windows, pas de mise à jour automatique.
- Échec si: des chiffres affichés ne correspondent pas à la base, ou un interrupteur de catégorie subsiste, ou l'interface gèle pendant la capture.

## Contraintes

- Règles du projet (CLAUDE.md): fonctions de 20 lignes maximum, modules de 200 lignes maximum, noms anglais explicites, constantes nommées, annotations de types, un module par couche et dépendances à sens unique, logique pure testable sans Tk ni SQLite pour les calculs, tests pytest sur données synthétiques, dépendances dans `requirements.txt` et le venv.
- La capture et l'écriture en base continuent de tourner en arrière-plan sans bloquer l'interface; l'interface lit la base en lecture seule.
- Style: pas de « · » comme séparateur, pas de triangles ▸ dépliants, libellés et valeurs séparés proprement.
- Fenêtre: taille minimale 760×480; de 1100 px de large et plus, la fiche de détail est à droite du tableau, en dessous sinon; sous 760 px le menu passe en barre horizontale en haut.

## Les vues (décisions du propriétaire sauf mention « choix de Claude »)

**Menu et état.** Menu à gauche (220 px): HDV, Brisage, Familiers, Logs, Réglages. En bas du menu, l'état de la capture: point vert « Capture active », Serveur, compteurs Prix, Brisages, Familiers, Dernier relevé. Le bouton Arrêter / Relancer reste sous cet état (choix de Claude, il existe déjà).

**Boutons de durée, communs à HDV, Brisage, Familiers et Logs:** Dernière heure, 6 heures, Aujourd'hui, 7 jours, 30 jours, Tout, Personnalisé (deux dates). Chaque vue garde son propre choix. Le filtre porte sur la date de capture de la donnée (le moment où le client l'a vue). « Aujourd'hui » commence à minuit, heure locale (choix de Claude). Valeur par défaut: Aujourd'hui (choix de Claude).

**Dates dans les tableaux** (HDV, Brisage, Familiers): affichées en durée écoulée, « il y a 12 min » sous une heure, « il y a 3 h » sous un jour, « il y a 2 j » ensuite; la date exacte (jour et heure locale) s'affiche au survol. Les colonnes s'appellent « Dernier relevé » (HDV, Familiers) et « Il y a » (Brisage). Le tri se fait sur la date réelle, pas sur le texte. Les Logs gardent l'heure exacte, et les listes des fiches gardent des dates exactes (choix de Claude).

**Barre de filtres.** Recherche par nom (objet ou ressource) et boutons de durée. Le serveur n'est pas un filtre des vues: il se règle uniquement dans les Réglages, et les vues n'affichent que les données du serveur choisi (décision du propriétaire). Tri par clic sur un en-tête de colonne.

**HDV.** Tableau, une ligne par objet: Objet, Type, Dernier prix ×1, Médian 24 h, Vendus 24 h, Dernière date. Tri par défaut: dernière date, la plus récente d'abord. Fiche à droite: nom, niveau, type; Médian, Moyen, Vendus; courbe des prix avec onglets 24 h, 7 j, 30 j, axe des prix, axe des dates, infobulle au survol (date, prix, objets vendus) à partir des points stockés dans `market_stats`; prix par lot (×1, ×10, ×100) du dernier relevé; historique de tous les relevés de prix de lot de l'objet avec leur date (c'est « l'ensemble des prix trouvables pour un objet»).

**Brisage.** Tableau, une ligne par objet brisé: Il y a (durée écoulée), Objet, Quantité, Coefficient (en %), **Valeur estimée de l'objet**, **Valeur HDV de l'objet**, **Valeur estimée des runes**, **Plus-value** (en kamas). La colonne « Runes obtenues » est supprimée du tableau (inutile, demande du propriétaire); les runes restent détaillées dans la fiche. Valeur estimée de l'objet = prix moyen 24 h × quantité (comme l'estimation du jeu); Valeur HDV de l'objet = dernier prix HDV × quantité (interprétation de Claude de « valeur estimée de l'objet + colonne valeur HDV », à confirmer par le propriétaire); la plus-value utilise la valeur HDV. **Tri par défaut: Plus-value, la plus haute d'abord** (le propriétaire a demandé « filtré sur ça par défaut »; compris comme un tri, aucune ligne n'est masquée: choix de Claude). La plus-value est verte si elle est positive, rouge sinon. Fiche: dernier coefficient, moyen, nombre de brisages; courbe du coefficient dans le temps (datée, infobulle avec le nombre de runes); runes du dernier brisage avec, pour chacune, sa quantité et sa valeur estimée, puis la valeur estimée totale des runes, la valeur estimée de l'objet et la plus-value du dernier brisage.

Valeur estimée de l'objet: prix de l'objet brisé selon le même réglage de prix que ci-dessous, multiplié par la quantité brisée (lot ×1 de l'objet; objet sans prix connu: « Inconnu »). Plus-value = valeur estimée des runes − valeur estimée de l'objet; elle n'est calculée que si le prix de l'objet est connu, sinon « Inconnu » (les lignes sans plus-value sont en fin de liste).

Valeur estimée des runes (nécessaire, demandée par le propriétaire): somme, sur les runes obtenues, de la quantité × le prix d'1 rune, selon le même réglage « Prix utilisé pour les estimations » que les familiers (dernier prix HDV par défaut; le plus petit lot divisé par sa taille s'il n'y a pas de lot ×1). Calcul avec toutes les décimales, affichage en kamas entiers avec espaces. Une rune sans prix connu compte pour 0 et la valeur est alors marquée « partielle » (choix de Claude); si aucune rune n'a de prix, la valeur affiche « Inconnu ».

**Familiers.** Tableau, une ligne par **ressource** donnée aux familiers: Ressource, Type, Prix d'1 ressource, XP pour 1 ressource, **Kamas par XP** (colonne triée par défaut, la moins chère par XP d'abord, avec une barre comparative), Observations (nombre de dons de cette ressource), Dernière date, **Coût pour monter un familier** (dernière colonne). Une ressource sans prix connu affiche « Inconnu » et reste en bas. Fiche: XP pour 1 ressource, prix, kamas par XP, coût pour monter un familier, courbe des kamas par XP dans le temps, liste des améliorations observées (date, quantité, XP).

Règles de calcul (pures, testées):
- XP gagnée d'une amélioration = expérience après − expérience avant (l'expérience est cumulative).
- XP pour 1 ressource = somme des XP gagnées / somme des quantités, sur les améliorations faites avec **une seule ressource** (choix de Claude: avec plusieurs ressources l'XP de chacune n'est pas séparable; ces améliorations restent dans l'historique sans entrer dans le ratio). L'XP affichée par le jeu est un entier arrondi (9 Boue du Boo donnent +1): regrouper tous les dons d'une même ressource réduit l'erreur.
- Kamas par XP = prix d'1 ressource / XP pour 1 ressource. Coût pour monter un familier = kamas par XP × **179 591 XP** (constante fournie par le propriétaire, nommée `PET_TOTAL_EXPERIENCE`; à confirmer sur plusieurs familiers).
- Précision et affichage (décision du propriétaire, mise en forme choix de Claude): les observations et tous les calculs gardent leurs décimales (XP pour 1 ressource, kamas par XP, coût), rien n'est arrondi avant l'affichage ni avant le tri. L'affichage des prix de la vue Familiers est simplifié: kamas en nombres entiers avec espaces comme séparateur de milliers (prix d'1 ressource, coût pour monter un familier); kamas par XP en entier à partir de 10 et avec une décimale en dessous; XP pour 1 ressource en entier à partir de 1 (+30) et, en dessous de 1, sous la forme « 1 XP pour 9 » (l'inverse arrondi à l'entier) plutôt que « +0,11 ». Le tri et la barre comparative utilisent la valeur exacte; l'infobulle de la fiche peut montrer la valeur exacte.
- Améliorations inutilisables (choix de Claude): si l'expérience avant ou après est absente, ou si le gain est nul ou négatif (familier au niveau maximum, message mal lu), l'amélioration n'entre pas dans le ratio. Elle reste dans l'historique de la fiche (sans XP) et compte dans « Observations » (nombre de dons); le ratio n'utilise que les améliorations utilisables.
- Fiabilité (choix de Claude): une ligne dont l'XP totale observée est inférieure à 10 est marquée « peu fiable » (l'arrondi pèse plus de 5 %).
- Une ressource = une ligne, tous familiers confondus: on suppose que l'XP donnée par une ressource ne dépend ni du familier ni de son niveau (à confirmer par le propriétaire, voir ci-dessous). Le regroupement est isolé dans une seule fonction pure pour que le passage à une clé (familier, ressource) reste peu coûteux.
- Prix d'1 ressource (réglable, voir Réglages): par défaut le **dernier prix HDV** du lot ×1 de la ressource; s'il n'existe pas de lot ×1, le plus petit lot divisé par sa taille (choix de Claude).

**Logs.** Flux en direct, toujours affiché (l'interrupteur « Afficher les logs » disparaît), 200 dernières lignes, plus récentes en haut. Colonnes: Heure, Type (étiquette de couleur HDV, Brisage, Familier), Objet, Détail, Valeur. Filtres: recherche, type (Tout, HDV, Brisage, Familier), boutons de durée, bouton Vider (efface l'affichage, jamais la base). Les avis existants (« ressource inconnue », « reconnecte-toi ») restent.

**Réglages.** Cartes qui se réorganisent selon la largeur: Serveur de jeu; Base de données (emplacement, changer); Noms d'objets (nombre d'objets connus, date du dernier téléchargement, Télécharger les noms; la colonne de taux de recyclage reste dans le CSV et la table `items`); **Prix utilisé pour les estimations** (valable pour les familiers et pour les runes du brisage; Dernier prix HDV par défaut; autres choix proposés: Médian 24 h, Moyen 24 h, choix de Claude); Mises à jour (version installée, annonce et bouton « Mettre à jour et relancer » quand une version est disponible, jamais automatique); À propos (données collectées, aucun envoi à un serveur, licence « Tous droits réservés »).

## Dates et état de départ

Les dates de capture (`captured_at`) sont stockées en UTC (format ISO avec `Z`); l'interface les convertit en heure locale pour l'affichage et pour les durées (« Aujourd'hui » = depuis minuit local). Le plan part de l'arbre de travail actuel, pas de HEAD: il contient déjà la correction du prix 0 des statistiques HDV, le retrait de la collecte du recyclage et la suppression de ses tables (décisions du 2026-11-12).

## Version et remise à zéro des données

Cette refonte est livrée comme la **V2** du client (version du produit 2.0.0). Décision du propriétaire: faire une remise à zéro des prix et de **toutes les données collectées** de la base locale (prix de lots, statistiques de marché, brisages, améliorations de familiers). Les tables de référence (noms d'objets avec leurs taux, serveurs) ne sont pas des données collectées et sont conservées (choix de Claude; elles se retéléchargent de toute façon). La remise à zéro de la base du propriétaire est faite une fois, après une copie de sauvegarde horodatée de `prices.db`; les statistiques HDV déjà stockées sont en outre faussées pour les objets vendus à 0 kama (prix 0 mal lu avant la correction du 2026-11-12).

## Ce qui disparaît

Page Données et ses interrupteurs; le réglage `enabled_categories` du fichier de configuration (ignoré s'il est présent) et le filtrage par consentement à l'écriture (`FilteringWriter`, filtrage dans `run`); la page Accueil et ses compteurs; la page À propos (reprise en carte); le bouton « Voir les prix en ligne ». Le critère « le joueur peut désactiver chaque catégorie » (README, CLAUDE.md, notes du projet) est abandonné pour la collecte locale; le consentement pour la future synchronisation sera à décider à ce moment-là.

## Ce qui est laissé au constructeur

Choix de la technique d'affichage dans l'existant CustomTkinter (tableau triable et filtrable, courbes datées; pas de nouvelle dépendance lourde sans raison), découpage des modules, requêtes SQL et index, gestion de grands volumes (aucune pagination demandée; limiter l'affichage à un plafond avec un avis si besoin), rafraîchissement en direct des tableaux pendant la capture, nom du familier à partir de l'objet (`pet_item_id`) dans la table `items`, seuil exact des durées « Personnalisé », mise à jour de la documentation et des tests.
