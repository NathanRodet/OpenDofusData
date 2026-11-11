# Capturer et vérifier une catégorie (recyclage, brisage, familiers)

Les trois catégories sont décodées en bêta (voir [protocol-notes.md](protocol-notes.md)). Ce guide sert à les **valider avec d'autres cas** et à en capturer de nouvelles. Pour les familiers, lance `discover` avec `--max-fields 100000` AVANT de te connecter: l'inventaire de la connexion est nécessaire.

Les messages du jeu ont des noms obfusqués qui changent à chaque version, et leurs champs ne sont pas documentés. Un décodeur ne peut donc s'écrire qu'à partir d'une capture réelle: sans elle, il décoderait de travers sans aucune erreur visible, et la base contiendrait de fausses données. Cet outil réduit le travail à **deux captures et quelques nombres lus à l'écran** par catégorie.

## Ce que tu fais (par catégorie)

1. **Capture témoin** (30 secondes, aucune action en jeu). Dans PowerShell, à la racine du projet, venv actif, avant de te connecter ou en jeu sans toucher à rien:
   ```powershell
   opendofusdata discover --output captures\recyclage-temoin.jsonl
   ```
   `Ctrl+C` pour arrêter.
2. **Capture avec l'action**: relance `discover` avec un autre fichier (`captures\recyclage-action.jsonl`), fais UNE action de la catégorie (recycler un objet, briser un objet, nourrir un familier), puis `Ctrl+C`.
3. **Note les nombres affichés à l'écran** juste après l'action, dans un fichier texte `captures\recyclage-notes.txt`: l'identifiant ou le nom de l'objet, et chaque quantité, chaque valeur que le jeu affiche (ressources obtenues, runes, expérience, coefficients...). Plus il y a de nombres, plus l'identification est sûre. Une capture d'écran du résultat aide aussi.

Sans option, `discover` ne journalise que la structure des messages (types, tailles, numéros de champs, entiers): ni texte ni chat. Les journaux sont dans `captures/`, ignoré par git.

## L'analyse (je peux la lancer à ta place)

```powershell
opendofusdata analyze captures\recyclage-action.jsonl --baseline captures\recyclage-temoin.jsonl --values "33528,4,120" --skeleton
```

`--values` reçoit les nombres de ta note. La commande classe les messages de la capture: d'abord ceux qui contiennent le plus de tes nombres, puis ceux absents de la capture témoin. Pour chacun elle affiche où se trouve chaque nombre (`1.2` = champ 2 du message imbriqué dans le champ 1; `1.2#0` = premier nombre d'une liste compactée) et les nombres introuvables.

Si des nombres sont introuvables, c'est souvent qu'ils sont dans une liste compactée, visible seulement avec les octets: relance la capture avec `--hex-types NOM` (le nom court du message candidat) puis refais l'analyse. Ces aperçus d'octets peuvent contenir du texte de chat ou des identifiants si le message en transporte: relis le journal avant de le partager.

## Ce qui se passe ensuite

Il suffit de me dire que les fichiers sont dans `captures\`: je lance l'analyse, j'identifie le message, j'écris le décodeur, ses tests (sur des octets synthétiques tirés de ta capture) et l'enregistrement en base, puis je passe la catégorie à `available=True` dans `categories.py`: son interrupteur de la page Données devient actif. Tu vérifies ensuite en jeu en comparant les Logs de la fenêtre à ce que le jeu affiche. Le décodeur suit la structure de `hdv.py`:

1. Constantes du message dans `src/opendofusdata/messages.py`.
2. Module de décodage pur (sans Scapy ni SQLite), avec tests.
3. Enregistrement (dataclass dans `records.py`) et table dans `storage.py`.
4. Branchement dans `run_pipeline.py` et dans le fil de logs.
5. Champs vérifiés documentés dans `protocol-notes.md`, avec les octets et les valeurs lues à l'écran.
