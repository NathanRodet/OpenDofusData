# Interface du client joueur (fenêtre OpenDofusData): conception

Date: 2026-11-11. Remplace la petite fenêtre tkinter actuelle (`opendofusdata window`, [window_view.py](../../../src/opendofusdata/window_view.py)).

## Intention

Les joueurs installent le client pour contribuer aux données du jeu sans y penser. La fenêtre doit dire en un coup d'œil si la capture fonctionne, laisser le joueur contrôler ce qui est collecté, et lui montrer, s'il le veut, exactement ce que l'outil capte (et plus tard enverra). La transparence et le contrôle sont l'argument de confiance d'un outil libre qui lit le trafic réseau.

## Objectifs

- Fenêtre moderne en CustomTkinter, thème sombre unique, accent bleu.
- Menu latéral à gauche (largeur fixe) et cinq pages: Accueil, Données, Logs, Réglages, À propos.
- Fenêtre redimensionnable, taille minimale 640×400. La page reste dans une colonne centrée de 480 px maximum; les boutons ont une taille fixe; rien ne s'étire.
- Bouton Arrêter / Relancer toujours visible en bas du menu.

## Non-objectifs

- Pas de thème clair, pas de réglage de thème.
- Pas de zone de notification, pas de démarrage automatique avec Windows (inchangé).
- Pas d'envoi vers un serveur: la v1 n'envoie rien. L'onglet Logs montre ce qui est capté et enregistré; il montrera l'envoi quand il existera.
- Pas de nouveau décodeur: recyclage, brisage et pets restent « bientôt ».
- Pas de mise à jour automatique, jamais. Demande ajoutée après la conception, non construite dans cette livraison: quand une nouvelle version existe, la page À propos affiche un signe de notification et un clic récupère la version puis relance l'application. La source des versions (par exemple les Releases de https://github.com/NathanRodet/OpenDofusData), le format d'installation et la vérification d'intégrité restent à décider (voir [roadmap.md](../../roadmap.md)).

## Anti-objectifs (échec même si ça marche)

- Une fenêtre dont le contenu s'étire de façon laide quand on l'agrandit.
- Un onglet Logs qui expose du texte de chat, des identifiants de compte ou des adresses IP (il ne montre que les données de jeu déjà stockées: objets, prix, lots, horodatages).
- Une interface qui gèle pendant la capture ou l'arrêt.
- Des logs qui grossissent sans limite en mémoire.

## Pages

**Accueil.** Gros état (Capture active / arrêtée / erreur avec le message clair existant), serveur, enregistrements de la session (prix et statistiques), heure du dernier relevé, bouton « Voir les prix en ligne ». Textes issus de [window_format.py](../../../src/opendofusdata/window_format.py), conservés.

**Données.** Les quatre catégories (HDV, recyclage, brisage, pets) avec interrupteur et compteur. Seule l'HDV est décodée; les trois autres sont affichées « bientôt » et inactives. Voir « Question ouverte » pour le câblage des interrupteurs.

**Logs.** Un interrupteur « Afficher les logs », désactivé par défaut. Activé, il affiche le fil des données captées, une ligne par enregistrement, la plus récente en haut (ex. `14:32:05 · HDV · Ailes de Moskito · lot ×10 · 5 868`). Désactivé, rien n'est affiché et rien n'est accumulé pour l'affichage. Présentation en colonnes à largeur fixe: Heure, Type (catégorie), Objet (coupé avec « … » s'il est trop long, jamais de retour à la ligne), Détail (ex. `lot ×10`, `stats 7 j`), Valeur (alignée à droite). Le fil garde les 200 dernières lignes. Les noms d'objets viennent de la table `items` (sinon `N/A`), comme `prices`.

**Réglages.** Deux réglages: le serveur de jeu (liste existante de [game_servers.py](../../../src/opendofusdata/game_servers.py), mémorisé comme aujourd'hui) et l'emplacement de la base SQLite. Pas de réglage de thème. Un changement de serveur ou de base s'applique au prochain démarrage de la capture: la page le dit, et propose de relancer.

**À propos.** Nom, version, lien vers le dépôt (adresse à définir), rappel de ce qui est collecté et que rien n'est envoyé (v1).

## Contraintes

- CLAUDE.md: fonctions de 20 lignes, modules de 200 lignes, annotations de type, constantes nommées (tailles, 480, 640×400, 200 lignes), pas d'`except` nu.
- La logique pure (formatage, tampon de logs) ne dépend pas de tkinter ni de CustomTkinter et est testée avec des données synthétiques; la vue est mince. La vue est découpée en un module par page.
- Dépendance `customtkinter` ajoutée à `requirements.txt` et à `pyproject.toml`, installée dans le venv. Compatibilité avec Python 3.13 à vérifier avant d'implémenter.
- Le thread de capture ne touche jamais les widgets: la vue lit des instantanés (`snapshot()`) à intervalle régulier, comme aujourd'hui.
- Les logs de l'onglet se branchent au même point que les compteurs (`CountingWriter` dans [session_counters.py](../../../src/opendofusdata/session_counters.py)): un tampon borné, protégé par verrou.

## Décisions de mon côté (à relire)

- Thème sombre, accent bleu; menu de 130 à 160 px; boutons du menu 110×32, boutons de page 200×32.
- Cinq entrées dans le menu: Accueil, Données, Logs, Réglages, À propos.
- Tampon de 200 lignes pour les logs.
- Changer de serveur ou de base ne redémarre pas la capture à chaud: effet au prochain démarrage.
- La commande reste `opendofusdata window`; `run` en console est inchangé.

## Laissé au constructeur

Détail visuel (espacements, polices), structure interne des classes de page, mécanisme exact de rafraîchissement, tests de la vue.

## Interrupteurs de la page Données (décision: fonctionnels)

Décision prise par « avec tes choix » du propriétaire, sur ma recommandation: les interrupteurs fonctionnent dès cette livraison. Cela inclut le réglage `enabled_categories` dans `config.json` (par défaut seule `hdv` est active) et un filtre à l'entrée de la capture: une catégorie désactivée n'est ni enregistrée ni comptée ni affichée dans les logs (point « Catégories désactivables » de [roadmap.md](../../roadmap.md)). Les catégories sans décodeur (recyclage, brisage, pets) sont affichées « bientôt » et leur interrupteur est inactif. Désactiver l'HDV s'applique à la capture en cours.
