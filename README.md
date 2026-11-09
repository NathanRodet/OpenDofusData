# OpenDofusData

Outil local pour Windows qui capture le trafic réseau de Dofus 3 (TCP 5555), décode les messages de l'HDV et stocke les prix dans une base SQLite locale. Rien n'est envoyé vers un serveur externe.

> Statut: mise en place de l'environnement de développement. Le code de capture n'est pas encore écrit.

## Prérequis

- Windows 11
- Python 3.13
- [Npcap](https://npcap.com) 1.90 installé au niveau du système. Ne pas cocher « Restrict Npcap driver's access to Administrators only », sinon l'outil doit être lancé en administrateur. Le mode « WinPcap API-compatible » n'est pas nécessaire.
- Dofus 3 lancé sur la même machine que l'outil.

## Installation

Depuis PowerShell, à la racine du projet:

```powershell
.\dev.ps1 setup
```

Cette commande crée le venv `.venv` et installe `requirements.txt`. Pour l'activer dans ta session:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell refuse d'exécuter le script, lance une fois `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Npcap est installé au niveau du système: il fonctionne depuis le venv sans configuration.

## Script de dev

| Commande | Effet |
|---|---|
| `.\dev.ps1 setup` | Crée le venv et installe les dépendances |
| `.\dev.ps1 test` | Lance `pytest` dans le venv |
| `.\dev.ps1 clean` | Supprime le venv et les caches |
| `.\dev.ps1 help` | Affiche l'aide |

## Dépendances

Listées dans [requirements.txt](requirements.txt): `scapy` (capture) et `pytest` (tests). Le décodage Protobuf et SQLite utilisent la bibliothèque standard.

## Conventions de code

Voir [CLAUDE.md](CLAUDE.md): fonctions de 20 lignes maximum, modules de 200 lignes maximum, nommage explicite, annotations de type, tests `pytest`.
