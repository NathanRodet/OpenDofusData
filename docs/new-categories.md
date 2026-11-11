# Capturer une nouvelle catégorie (recyclage, brisage, pets)

Ce guide décrit comment obtenir ce qu'il faut pour écrire le décodeur d'une catégorie. Chaque catégorie suit la méthode utilisée pour l'HDV (voir [protocol-notes.md](protocol-notes.md)): on repère le message, on décode ses champs, puis on vérifie les valeurs contre l'écran du jeu.

## Ce qu'il faut fournir par catégorie

1. Un journal `discover` d'une session où tu fais UNE action de la catégorie, à un moment que tu notes (heure de la montre).
2. Une capture d'écran du jeu juste après l'action, avec les valeurs visibles (objet, quantités, expérience gagnée...). Ce sont elles qui servent à valider le décodage.
3. Le nom exact des objets en jeu (ou leur identifiant DofusDB).

## Faire la capture

Dans un terminal PowerShell, à la racine du projet (venv actif), AVANT de te connecter au jeu ou de faire l'action:

```powershell
opendofusdata discover --output captures\recyclage-1.jsonl
```

Sans option, le journal ne contient que la structure des messages (type, taille, champs): ni texte ni octets, donc rien de personnel. Fais l'action une seule fois (ouvrir la fenêtre de recyclage et recycler un objet, briser un objet, nourrir un familier), puis `Ctrl+C`. Note l'heure et le résultat affiché à l'écran.

Pour les messages repérés, le décodeur a besoin des octets: relance avec `--hex-types "nom1,nom2"` (les noms courts vus dans le premier journal). Attention: ces aperçus peuvent contenir du texte de chat ou des identifiants si le type de message en transporte. Relis le journal avant de le partager, et ne le partage pas s'il contient quelque chose de personnel (`captures/` est ignoré par git).

## Repérer le bon message

1. Fais d'abord une capture « témoin » de quelques secondes sans aucune action, puis la capture avec l'action.
2. Compare les types de message: ceux qui n'apparaissent qu'avec l'action sont les candidats. Les messages très fréquents (`jnz`, `kne`, `knb`...) sont du bruit.
3. Le nom d'un message change à chaque mise à jour du jeu: note la version du jeu dans le nom du fichier.

## Écrire le décodeur (pour le développement)

1. Ajouter les noms de message dans `src/opendofusdata/messages.py`.
2. Un module de décodage pur (sans Scapy ni SQLite), comme `hdv.py`, avec des tests sur des octets synthétiques.
3. Un enregistrement (dataclass dans `records.py`) et une table dans `storage.py`.
4. Brancher le décodeur dans `run_pipeline.py` et passer la catégorie à `available=True` dans `categories.py`: son interrupteur de la page Données devient actif.
5. Documenter les champs vérifiés dans `protocol-notes.md`, avec les octets et les valeurs lues à l'écran.
