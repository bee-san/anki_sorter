<p align="center">
  <img src="assets/anki-vn-sorter.svg" alt="Anki VN Sorter" width="100%">
</p>

<h1 align="center">Anki VN Sorter</h1>

<p align="center">
  <strong>Frequency-first new-card ordering for Japanese sentence decks.</strong><br>
  Make Anki introduce common, readable cards before rare or painful ones.
</p>

<p align="center">
  <a href="#install"><img alt="Install" src="https://img.shields.io/badge/install-.ankiaddon-6366F1"></a>
  <a href="https://github.com/bee-san/anki_sorter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/bee-san/anki_sorter/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/bee-san/anki_sorter/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/bee-san/anki_sorter?label=release&color=10B981"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776AB">
  <img alt="Frequency" src="https://img.shields.io/badge/frequency-Jiten%20%2B%20Yomitan-F59E0B">
  <img alt="Anki" src="https://img.shields.io/badge/Anki-add--on-2563EB">
</p>

<p align="center">
  <a href="#why">Why</a> ·
  <a href="#install">Install</a> ·
  <a href="https://github.com/bee-san/anki_sorter/releases/latest">Releases</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-sorts">How it sorts</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#development">Development</a>
</p>

---

## Why

Large Japanese sentence decks can be noisy: some new cards are common and readable, while others are rare, kana-heavy, or packed with unknown kanji. Default Anki ordering does not know the difference.

**Anki VN Sorter** adds a small ranking layer before new cards are shown:

| Without it | With Anki VN Sorter |
| --- | --- |
| New cards follow deck/insertion/random order. | New cards are reordered by frequency and readability. |
| Common but useful cards can be buried. | High-value cards rise earlier. |
| Unknown-kanji walls can appear too soon. | Known-kanji cards get a soft readability boost. |
| Reviews and learning cards risk being mixed into tooling. | Only matching **new** cards are repositioned. |

The default setup targets **Kiku** and **Lapis**-style Japanese sentence cards. Any similar note type can work if it has an expression field and, optionally, a `FreqSort` fallback field.

## What it does

- **Frequency-first ranking** — prioritizes cards with better ranks from the configured frequency source.
- **Readability-aware tie breaking** — prefers cards that use kanji you have already matured.
- **Kiku + Lapis defaults** — ships with sensible defaults for common Japanese sentence-card setups.
- **Safe scope** — only eligible new cards are repositioned; reviews, learning cards, and suspended cards are left alone.
- **Offline fallback** — uses cached/bundled data when the network is unavailable.
- **Desktop automation** — can run after Anki sync, which is safer for AnkiDroid workflows.
- **Manual controls** — sort, refresh, and switch frequency sources from Anki's Tools menu.
- **Local API** — exposes `GET /health` and `POST /sort` for scripts and optional timers.

## Install

Install the packaged add-on from the latest GitHub Release:

1. Download `anki_vn_sorter.ankiaddon` from [the latest release](https://github.com/bee-san/anki_sorter/releases/latest).
   - Direct download: [`anki_vn_sorter.ankiaddon`](https://github.com/bee-san/anki_sorter/releases/latest/download/anki_vn_sorter.ankiaddon)
   - Do not install GitHub's source-code ZIP; use the `.ankiaddon` asset.
2. Open Anki Desktop.
3. Go to `Tools -> Add-ons -> Install from file...`.
4. Select the downloaded `anki_vn_sorter.ankiaddon`.
5. Restart Anki.

Release packages are built by GitHub Actions. Pull requests and pushes to `main` also build the `.ankiaddon` as a CI artifact.

For development, link the source folder into Anki's add-on directory:

```bash
# macOS
mkdir -p "$HOME/Library/Application Support/Anki2/addons21"
ln -sfn "$PWD/addon/anki_vn_sorter" "$HOME/Library/Application Support/Anki2/addons21/anki_vn_sorter"

# Linux
mkdir -p ~/.local/share/Anki2/addons21
ln -sfn "$PWD/addon/anki_vn_sorter" ~/.local/share/Anki2/addons21/anki_vn_sorter
```

On Windows, place or link `addon/anki_vn_sorter` under `%APPDATA%\Anki2\addons21\anki_vn_sorter`.

## Quick start

1. Install the add-on and restart Anki.
2. Open the profile that contains your Japanese sentence deck.
3. Make sure your target cards match the scope query:

   ```text
   (note:"Kiku" or note:"Lapis") is:new -is:suspended
   ```

4. Run `Tools -> Anki VN Sorter -> Sort VN Cards Now`.
5. Optional: run `Tools -> Anki VN Sorter -> Refresh Current Frequency Source Now`.

The default automation mode is:

```json
{
  "autoSortMode": "after_sync"
}
```

That means Anki Desktop reorders new cards after sync completes. If you also study on AnkiDroid, this avoids racing mobile changes.

## How it sorts

The recommended strategy is `frequency_first_soft_v1`.

For each eligible new card, the add-on:

1. reads the expression field,
2. looks up a frequency rank,
3. infers known kanji from matured cards,
4. blends frequency with a soft readability multiplier,
5. repositions matching new cards through Anki's internal scheduler API.

Default scoring shape:

| Card shape | Treatment |
| --- | --- |
| All kanji known | full frequency value |
| Kana-only | small configurable penalty |
| Unknown kanji | configurable penalty per unknown kanji |
| Partially-known kanji word | tiny coverage bonus |

Final ordering uses score first, then raw rank, expression length, current due position, template order, and card id for stable tie-breaking.

## Configuration

Open `Tools -> Add-ons -> Anki VN Sorter -> Config` inside Anki.

Recommended default core settings:

```json
{
  "modelNames": ["Kiku", "Lapis"],
  "scopeQuery": "(note:\"Kiku\" or note:\"Lapis\") is:new -is:suspended",
  "expressionField": "Expression",
  "freqSortField": "FreqSort",
  "strategy": "frequency_first_soft_v1",
  "autoSortMode": "after_sync"
}
```

Using a different but similar note type? Add it to both `modelNames` and `scopeQuery`:

```json
{
  "modelNames": ["Kiku", "Lapis", "My Sentence Card"],
  "scopeQuery": "(note:\"Kiku\" or note:\"Lapis\" or note:\"My Sentence Card\") is:new -is:suspended"
}
```

Important settings:

| Setting | Purpose |
| --- | --- |
| `modelNames` | Note types the sorter is allowed to touch. |
| `scopeQuery` | Anki search query for eligible new cards. |
| `matureDays` / `matureQuery` | Which cards count as known-kanji evidence. |
| `expressionField` | Field containing the Japanese expression. |
| `freqSortField` | Optional deck-provided frequency fallback. |
| `autoSortMode` | `after_sync`, `profile_open`, or `manual_only`. |
| `jitenFrequencyListId` | Built-in Jiten list: `global`, `visual_novel`, `novel`, `anime`, etc. |
| `yomitanFrequencyIndexUrl` | Optional Yomitan frequency dictionary URL. |

## Frequency sources

By default, the add-on uses Bee's updateable Yomitan frequency dictionary and falls back to cached/bundled data when needed. You can switch to a built-in Jiten list from:

```text
Tools -> Anki VN Sorter -> Choose Jiten Frequency List...
```

Attribution: frequency data is derived from [Jiten](https://jiten.moe/). Jiten frequency data is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Keep `addon/anki_vn_sorter/data/ATTRIBUTION.md` with redistributed packages.

## Menus and API

Anki menu actions:

- `Tools -> Anki VN Sorter -> Sort VN Cards Now`
- `Tools -> Anki VN Sorter -> Choose Jiten Frequency List...`
- `Tools -> Anki VN Sorter -> Set Yomitan Frequency Dictionary URL...`
- `Tools -> Anki VN Sorter -> Clear Yomitan Frequency Dictionary URL`
- `Tools -> Anki VN Sorter -> Refresh Current Frequency Source Now`

Local endpoints while Anki is running:

```bash
curl http://127.0.0.1:8767/health
curl -X POST http://127.0.0.1:8767/sort
```

Optional helper script:

```bash
python3 scripts/request_sort.py --force
```

## Deck behavior

The add-on repositions new cards. It does not touch review or learning cards, and it does not override Anki's scheduler.

For the sorted order to show reliably, deck options should preserve gathered order. `/health` reports warnings when deck options look incompatible with manual repositioning.

## Optional systemd timer

The default `after_sync` mode is best for most desktop + AnkiDroid workflows. If you still want a timer, templates live in `systemd/`:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/anki-vn-sorter.service ~/.config/systemd/user/
cp systemd/anki-vn-sorter.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now anki-vn-sorter.timer
```

The timer only works while Anki is running and the target profile is open.

## Development

Run the test suite:

```bash
python3 -m unittest discover -s tests
```

Compile check:

```bash
python3 -m compileall addon scripts tests
```

Rebuild the add-on package:

```bash
python3 scripts/package_addon.py
```

Repo layout:

| Path | Purpose |
| --- | --- |
| `addon/anki_vn_sorter/` | Anki add-on source. |
| `addon/anki_vn_sorter/data/` | Bundled fallback frequency data and attribution. |
| `scripts/package_addon.py` | `.ankiaddon` package builder. |
| `scripts/request_sort.py` | Optional local API helper. |
| `systemd/` | Optional user timer templates. |
| `tests/` | Unit tests. |

## Troubleshooting

If sorting does nothing:

- confirm Anki is running and the correct profile is open,
- confirm target cards match `scopeQuery`,
- confirm each note has the configured `Expression` field,
- check `curl http://127.0.0.1:8767/health`.

If frequency ranking is missing:

- run `Tools -> Anki VN Sorter -> Refresh Current Frequency Source Now`,
- confirm the configured Yomitan/Jiten source can be reached,
- confirm bundled snapshots are present under `addon/anki_vn_sorter/data/`,
- confirm your notes have `FreqSort` if you rely on the deck fallback.

If the study order still looks wrong:

- inspect deck-option warnings from `/health`,
- make sure your deck is not randomizing new cards,
- confirm the target cards are still new after sync.
