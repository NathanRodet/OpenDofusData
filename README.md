<div align="center">

# OpenDofusData

**Turn your Dofus 3 play session into market data you can act on.**

A small Windows app that passively reads Dofus network traffic and stores prices, breaking results and pet XP in a database on your own computer.

[![Latest release](https://img.shields.io/github/v/release/NathanRodet/OpenDofusData?label=release&color=3b8ed0)](https://github.com/NathanRodet/OpenDofusData/releases/latest)
![Platform](https://img.shields.io/badge/platform-Windows%2011-3b8ed0)
![Data stays local](https://img.shields.io/badge/data-stays%20on%20your%20PC-2fb36d)
![License](https://img.shields.io/badge/license-all%20rights%20reserved-lightgrey)

[Download](https://github.com/NathanRodet/OpenDofusData/releases/latest) | [Install](#install) | [Features](#features) | [Privacy](#privacy)

</div>

> **Sharing prices starts when you enter a synchronization key.** Without a key, everything stays on your machine. With the key given to you by the server owner, saved in **Réglages**, the app sends the market prices you see to a sync server and fetches the ones other players sent; remove the key to stop. It only ever carries game data (never personal information); see [Privacy](#privacy) for exactly what is sent.

---

## Install

> **Only download OpenDofusData from the [Releases page of this repository](https://github.com/NathanRodet/OpenDofusData/releases/latest).** We suggest you never download this tool, or a similar version of it, anywhere else: it could have been corrupted with bad intentions. The app is not code-signed, so the SHA-256 check below and the source of the download are your only protection.

**Requirements:** Windows 11 and [Npcap](https://npcap.com). No Python needed.

**1. Install Npcap**

Download and install [Npcap](https://npcap.com). It is not bundled with OpenDofusData.

- Leave *"Restrict Npcap driver's access to Administrators only"* **unchecked**, otherwise run OpenDofusData as administrator.
- The *"WinPcap API-compatible mode"* is not needed.

**2. Download the app**

Get `OpenDofusData.exe` from the [latest release](https://github.com/NathanRodet/OpenDofusData/releases/latest).
To verify the download, compare it with the SHA-256 in `OpenDofusData.exe.sha256`:

```powershell
Get-FileHash OpenDofusData.exe
```

**3. Run it before you log in to the game**

Double-click `OpenDofusData.exe`. The app is not code-signed, so Windows SmartScreen may show *"Windows protected your PC"*: click **More info**, then **Run anyway**.

**4. Pick your game server**

Open **Réglages** and choose your server (the traffic does not reveal it). Capture restarts by itself with your choice. Optionally click **Télécharger les données de référence** to show item names instead of numbers and to fill the Craft and Brisage pages (recipes and effects).

That's it: play, and the pages fill up.


## Features

OpenDofusData listens while you play and turns what it understands into tables, charts and estimates.

| Page | What you get |
|---|---|
| **HDV** (market) | Every item whose listing you opened: latest price, 24 h median, units sold, 24 h / 7 d / 30 d price curves, lot prices ×1 / ×10 / ×100 / ×1000 and the full history of snapshots. |
| **Brisage** (breaking) | Your breakings, item by item: lowest market price, average breaking coefficient and average plus-value (value of the runes obtained minus the item price). Click an item to see the plus-value rune by rune, in classic breaking and in focus on the most profitable stat. |
| **Craft** | Every craft whose prices are all known, from most to least profitable, with the detail of its resources. Tick *Afficher les crafts incomplets* to also list the crafts with a missing price (the detail says which), and mark crafts as **favorites** (stored locally): a favorite stays listed even when a price is missing, and *Favoris seulement* keeps only them. |
| **Familiers** (pets) | How much XP a resource gives a pet and what one XP point costs you, cheapest first. Add your own observed XP for *x* resources, see the **price stop** at 25 kamas per XP, mark resources as **favorites** (stored locally, with a "favorites only" filter), and open the **Coverage** tab to see how many resources have a known coefficient and which ones are still missing (filterable by category). |
| **Logs** | What is being captured right now, filterable by type, period and name. |
| **Réglages** (settings) | Game server, database location, item names, the price used for estimates, the synchronization key (connection test), the optional purge of old local data, updates. |

Every page can be filtered with the period dropdown (last hour, 6 hours, today, 7 days, 30 days, all time, or a custom range), sorted by clicking a column header, and only shows the server you picked.

> **Beta:** breaking and pet data were validated on the captures of a single player. Compare what you see with the game screen.

## Using it

- **Start the app before you log in to Dofus**, then play normally. You can leave the window open in the background; closing it stops the capture. It does not start with Windows.
- **Market:** only the items whose listing you open are recorded.
- **Pets:** the app needs the inventory sent at login to recognize resources. If the Logs say *"reconnecte-toi au jeu"*, log out and back in once the app is running.
- **Breaking and crafts:** some estimates need reference data (item effects, runes, recipes) downloaded once from the public DofusDB API. See the [developer documentation](docs/developpement.md) (in French).
- The bottom of the left menu shows the capture status (running, stopped, or a clear error such as *Npcap missing*), your server and the **Stop / Restart** button.

## Where your data lives

Everything is in `%APPDATA%\OpenDofusData`:

| File | Content |
|---|---|
| `prices.db` | Your SQLite database (location can be changed in Réglages) |
| `config.json` | Your settings |
| `opendofusdata.log` | Technical log |

## Updates

Updates are **never automatic**. At startup the app asks GitHub whether a newer version exists (one anonymous request, can be turned off in Réglages). If there is one, a blue dot appears next to **Réglages**. Click **Mettre à jour et relancer** to download it, verify its SHA-256 checksum and restart. Since the app is not code-signed, only update from the Releases of this repository.

## Privacy

- Only game data is stored: item IDs, prices, quantities, timestamps and the game server you chose.
- IP addresses, accounts, character names and chat are **never stored or sent**.
- **Game data leaves your machine only once you save a synchronization key.** The only network requests the app makes by itself are the update check (`api.github.com`, can be disabled) and, only if you click *Télécharger les données de référence*, the download of item names, servers, recipes and effects from `api.dofusdb.fr`.
- **Synchronization** needs a key given to you by the server owner. Saving it in **Réglages** switches sharing on: the app then sends, for each item you looked at in the market, its item ID, lot size (x1, x10, x100, x1000), total price, the time you saw it and the game server you chose, with your key in the request header, and downloads what the others sent. Removing the key stops it. *Tester la connexion* sends your key, and nothing else, only when you click.
- **What other players see:** each price you send carries the 11-character code of your key. It is a pseudonym that lets the server owner revoke a key (and optionally delete its prices); it is not linked to your account or your character. The server keeps prices for 14 days, and a new or emptied database gets your own prices of those days back the first time it synchronizes. Your IP address is never stored and never read by the server application.
- The source code is public so this behavior can be verified.

## Known limitations

- Dofus message names change with game updates. After a game update the app may stop decoding until a new version is released (see the [developer documentation](docs/developpement.md)).
- Only the market, breaking and pets are decoded. No purchases, sales or price changes.
- An item with no offer on the market is not recorded: no snapshot does not mean a price of 0.
- The game server is not detected automatically: you choose it.

## Learn more

*The following documents are written in French.*

- [Developer documentation](docs/developpement.md): running from source, commands, building and releasing.
- [Roadmap](docs/roadmap.md) and [protocol notes](docs/protocol-notes.md).

## License

All rights reserved. The code is published on GitHub so it can be read and verified, but no license allows reusing, modifying or redistributing it without the author's permission.
