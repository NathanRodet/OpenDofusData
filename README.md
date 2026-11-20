# OpenDofusData

Client Windows qui observe, pendant que le joueur joue à Dofus, les données du marché (HDV) et du brisage affichées par le jeu, les analyse et les envoie à un serveur de collecte, pour qu'elles soient consultables par tous les joueurs sur un site web.

Version en cours de développement: **2.4.0** (réécriture en Tauri 2). La version 2.3 (Python) reste dans l'historique git, sous le tag `pre-tauri-rewrite`.

## Ce que fait le client

- Lit le trafic réseau du jeu (TCP 5555) avec Npcap, sans rien modifier ni injecter.
- Décode uniquement ce qui sert: les offres et les prix de l'HDV, et le résultat des brisages.
- Envoie ces données au serveur avec la clé du joueur. Aucun texte de chat n'est lu, enregistré ni envoyé.
- Aucune adresse IP de joueur n'est collectée, enregistrée ni transmise.
- N'envoie rien tant qu'aucune clé n'est enregistrée. Le joueur voit dans la page Logs le JSON exact de chaque envoi.

## État d'avancement

| Partie | État |
|---|---|
| Interface (React, TypeScript) | Terminée, branchée sur l'application (en navigateur seul, elle garde les données simulées) |
| Décodage des messages (Rust) | Terminé et validé sur des captures réelles |
| Format d'échange avec le serveur | Spécifié et testé (`odd-core`) |
| Capture réseau (Npcap) | Écrite et testée sur du vrai trafic (programme séparé `odd-capture-worker`) |
| Reconstruction TCP, circuit de décodage | Terminés, testés de bout en bout sur les captures de référence |
| Envoi au serveur (file, lots, nouvelles tentatives) | Terminé et testé |
| Application Tauri (réglages, état, test de connexion, logs en direct) | Terminée, testée contre le vrai serveur en HTTPS |
| Données de référence (DofusDB): 21 622 objets, copie locale rafraîchie chaque semaine | Fait, testé sur le vrai DofusDB |
| Installateur (NSIS, sans droits administrateur) et mise à jour: GitHub Release, SHA-256 vérifié, installation et relance en un clic | Fait, publication par étiquette `vX.Y.Z` (jamais testée sur GitHub) |

Pas encore testé avec le jeu lancé : le trafic réel du jeu n'a traversé le circuit que sous forme de captures rejouées.

## Organisation du dépôt

- `src/`: interface React et TypeScript.
- `src-tauri/`: application Tauri et crates Rust.
  - `crates/odd-core`: format des objets échangés avec le serveur (partagé avec lui).
  - `crates/odd-wire`: protobuf, découpage des trames, resynchronisation bornée du flux.
  - `crates/odd-decode`: décodeurs des messages de l'HDV et du brisage.
  - `crates/odd-tcp`: lecture des paquets et reconstruction des flux TCP.
  - `crates/odd-capture`, `crates/odd-capture-worker`: la capture Npcap (programme séparé, seul lié à Npcap) et son transport.
  - `crates/odd-agent`: du paquet brut aux objets décodés, puis à l'envoi.
  - `crates/odd-sync`: file d'envoi (donnée la plus fraîche), lots, nouvelles tentatives.
  - `crates/odd-service`: la logique de l'application derrière l'interface (réglages, état, test de connexion).
- `docs/`: décisions, schémas JSON, inventaire des champs (documentation privée, non versionnée).
- `captures/`: captures réelles du jeu servant de jeux d'essai (non versionnées).

## Prérequis

- Windows 10 ou 11 (64 bits), avec WebView2 (présent sur Windows 11 et sur les Windows 10 à jour).
- [Npcap](https://npcap.com/) pour la capture réseau. Aucun droit administrateur n'est requis.
- Pour développer: Node.js, Rust (édition 2024) et les outils de build C++ de Visual Studio. Le programme de capture se lie à `wpcap.lib`, que `scripts/make-wpcap-lib.ps1` fabrique depuis le Npcap installé (sans télécharger le SDK).

## Développement

Les commandes Tauri se lancent dans **PowerShell**, pas dans Git Bash (le `link` de Git Bash masque celui de Visual Studio).

```powershell
npm install
npm run worker         # construit le programme de capture (aussi lancé par tauri dev et tauri build)
npm run tauri dev      # application en mode développement
npm test               # tests de l'interface
npm run tauri build    # exécutable de production
npm run tauri icon src-tauri/icons/source/app-icon.svg   # régénère les icônes

cd src-tauri
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
```

## Règles de code Rust

`unsafe` est interdit. `unwrap`, `expect` et `panic` sont refusés hors des tests. Le détail est dans `CLAUDE.md`.

## Droits

Tous droits réservés. Le code est visible, mais aucune licence d'utilisation, de modification ou de redistribution n'est accordée.
