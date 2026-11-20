<div align="center">

# OpenDofusData

**Turn your Dofus 3 play session into market data you can act on.**

A small Windows app that passively reads Dofus network traffic, decodes the market (HDV) and breaking (brisage) results the game already shows you, and sends them to the OpenDofusData server, so every player can browse them on the website.

![release](https://img.shields.io/github/v/release/NathanRodet/OpenDofusData?label=release&color=3b82c4)
![platform](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011-3b82c4)
![privacy](https://img.shields.io/badge/privacy-no%20IP%2C%20no%20chat-2ea66a)
![license](https://img.shields.io/badge/license-all%20rights%20reserved-lightgrey)

[Download](#download) | [Install](#install) | [Features](#features) | [Privacy](#privacy) | [Development](#development)

</div>

## Download

Get the latest installer from the [Releases page](https://github.com/NathanRodet/OpenDofusData/releases/latest). The installer does not need administrator rights.

## Install

1. Install [Npcap](https://npcap.com/), which the app uses to watch the game traffic. Windows 10 and 11 (64 bits) are supported, with WebView2 (already on Windows 11 and on up to date Windows 10).
2. Run the OpenDofusData installer.
3. Sign in on the website with Discord, create your API key and paste it into the app. One key per account, valid for one week.
4. Play. Prices and breaking results you open in game are read and sent in the background.

Nothing is sent until a key is saved.

## Features

- **Market prices.** Lots and offers of the HDV, with the effects of each item, so the website can show the cheapest offers and the price history.
- **Breaking results.** What a breaking gives, to estimate its value.
- **See what is sent.** The Logs page shows the exact JSON of every upload.
- **Choose what you share.** Each category of data can be switched off on its own.
- **Updates under your control.** The About page tells you when a newer release exists. One click downloads it, checks its SHA-256, installs it and restarts the app. Nothing updates by itself.
- **Reference data.** Item names come from DofusDB, copied locally and refreshed every week.

## Privacy

- The app only reads the traffic of the game (TCP port 5555). It changes and injects nothing.
- Only the HDV and breaking messages are decoded. No chat text is read, stored or sent.
- No player address (IPv4 or IPv6) is collected, stored, logged or sent. The server does not log addresses either.
- Your API key is stored in your own configuration file on your computer.

## Development

Requirements: Node.js, Rust (edition 2024), the C++ build tools of Visual Studio, and Npcap. The capture program links to `wpcap.lib`, which `scripts/make-wpcap-lib.ps1` builds from the installed Npcap (no SDK download).

Run Tauri commands in **PowerShell**, not in Git Bash (the `link` of Git Bash hides the one of Visual Studio).

```powershell
npm install
npm run tauri dev      # development app (builds the capture worker first)
npm test               # interface tests
npm run tauri build    # production installer

cd src-tauri
cargo fmt --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace --all-features
```

### Repository layout

- `src/`: the React and TypeScript interface.
- `src-tauri/`: the Tauri app and the Rust crates.
  - `odd-core`: format of the objects exchanged with the server (shared with it).
  - `odd-wire`: protobuf, frame splitting, bounded resynchronisation of the stream.
  - `odd-decode`: decoders of the HDV and breaking messages.
  - `odd-tcp`: packet reading and TCP stream reassembly.
  - `odd-capture`, `odd-capture-worker`: the Npcap capture (a separate program, the only one linked to Npcap) and its transport.
  - `odd-agent`: from raw packet to decoded objects, then to upload.
  - `odd-sync`: upload queue (freshest data first), batches, retries.
  - `odd-service`: the app logic behind the interface (settings, state, connection test).

Rust rules: `unsafe` is forbidden, and `unwrap`, `expect` and `panic` are denied outside tests. Both are enforced by the compiler and clippy.

## License

All rights reserved. The code is visible, but no license to use, modify or redistribute it is granted.
