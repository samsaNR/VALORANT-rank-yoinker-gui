<p align="center">
    <img src="assets/Logo.png" alt="vRY GUI" width="160" height="160">
</p>

<h2 align="center">vRY GUI &mdash; VALORANT lobby insights</h2>

<p align="center">
    <a href="https://t.me/rinonrc">
        <img alt="Telegram" src="https://img.shields.io/badge/telegram-%40rinonrc-26a5e4?style=for-the-badge&logo=telegram&logoColor=white">
    </a>
    <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white">
    <img alt="Qt" src="https://img.shields.io/badge/PySide6-Qt%206-41cd52?style=for-the-badge&logo=qt&logoColor=white">
    <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-0078d4?style=for-the-badge&logo=windows&logoColor=white">
</p>

A modern dark-themed Qt window for VALORANT pre-game / in-game lobbies.
Pulls live data straight from your local Riot client and renders it as
sortable cards, charts and history pages &mdash; everything you'd see in a
console tracker, but in a real UI.

---

## Table of contents

1. [Highlights](#highlights)
2. [Screenshots](#screenshots)
3. [Quick start](#quick-start)
4. [Building a Windows .exe](#building-a-windows-exe)
5. [Storage layout](#storage-layout)
6. [Author](#author)
7. [Disclaimer](#disclaimer)

## Highlights

- **Live tracker** &mdash; rank icons, peak rank icons, agent portraits,
  RR with &plusmn;RR for the last competitive match, win %, headshot %,
  K/D and account level. Stats are colour-graded so the table reads at
  a glance.
- **Party indicator** &mdash; players in a premade group are tagged with a
  colour-coded `P1`/`P2` pill so you can see partied duos and trios
  instantly. Your own row is highlighted in red.
- **Team grouping** &mdash; rows are grouped under `BLUE TEAM` /
  `RED TEAM` banners and sorted by rank inside each group.
- **Loadouts** &mdash; every player's full inventory in one view (every
  weapon's skin icon, buddy charms, sprays and title), grouped by team
  and outlined by skin rarity (Select / Deluxe / Premium / Exclusive /
  Ultra).
- **Match history** &mdash; your past competitive matches recorded
  locally in `stats.json`, with map / agent / rank / RR / &plusmn;RR.
- **Stats &amp; charts** &mdash; RR-over-time chart plus winrate tables
  per agent and per map.
- **Game chat** &mdash; in-match chat panel with team / all / party
  pills, persisted to disk so the history survives restarts. The whole
  panel can be hidden when you need more table room.
- **Hover preview** &mdash; hovering a player reveals a rich card with
  agent / rank icons, last match info, &plusmn;RR and "played with you"
  counter.
- **Diamond+ glow** &mdash; rows for Immortal/Radiant players are
  subtly highlighted.
- **Sound notifications** for match start / end.
- **Collapsible sidebar** for small monitors.
- **Tray integration** &mdash; minimise to tray, restore via hotkey
  (`Ctrl+Shift+V` by default).
- **Right-click menu** &mdash; copy name, open in tracker.gg / blitz.gg,
  jump to a player's loadout card.

## Screenshots

> _Add your own screenshots to the `assets/` folder and reference them
> here, e.g. `![Tracker](assets/tracker.png)`._

## Quick start

VALORANT must be open while the tracker runs.

### Run from source (development)

```cmd
git clone https://github.com/samsaNR/VALORANT-rank-yoinker-gui.git
cd VALORANT-rank-yoinker-gui
python -m pip install -r requirements.txt
python gui.py
```

Or simply double-click `START_GUI.bat`.

Python **3.10 or newer** is required (PySide6 dependency).

### Run a packaged release

1. Download the latest release (or build it yourself, see below).
2. Extract the folder and double-click `vry-gui.exe`.

## Building a Windows .exe

Uses [`cx_Freeze`](https://cx-freeze.readthedocs.io/):

```cmd
python -m pip install -r requirements.txt
python -m pip install cx_Freeze
python setup.py build
```

The build output ends up under `build/exe.win-amd64-3.XX/`:

- `vry-gui.exe` &mdash; the GUI (this is the one you run).
- `vry.exe` &mdash; the underlying tracker process (started automatically
  when you click "Start tracker").

Run `vry-gui.exe` from inside the `build` folder &mdash; the Qt DLLs and
asset files live next to it.

## Storage layout

All persistent state stays on your machine:

| File | Purpose |
| --- | --- |
| `%APPDATA%\vry\stats.json` | Recorded competitive matches (used by History / Stats / &plusmn;RR fallback). |
| `%APPDATA%\vry\accounts.json` | Riot accounts the tracker has authenticated with. |
| `%APPDATA%\vry\chat_history.json` | In-match chat history (last 200 messages). |
| `%APPDATA%\vry\sounds\` | Generated `match_start.wav` / `match_end.wav` chimes. |
| `%APPDATA%\vry\img-cache\` | Cached agent / rank / skin / player-card icons. |

Delete any of these to reset that piece of state.

## Author

Built and maintained by **[@rinonrc](https://t.me/rinonrc)** on Telegram.
Pull requests / bug reports welcome on the
[GitHub repo](https://github.com/samsaNR/VALORANT-rank-yoinker-gui).

## Disclaimer

THIS PROJECT IS NOT ASSOCIATED WITH OR ENDORSED BY RIOT GAMES. Riot
Games and all associated properties are trademarks or registered
trademarks of Riot Games, Inc.

Effort has been made to abide by Riot's API rules &mdash; vRY GUI only
reads data from your own local Riot client and never modifies game
state. Use at your own risk.
