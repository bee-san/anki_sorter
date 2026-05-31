# Anki VN Sorter

Frequency-aware new-card ordering for Kiku decks, built for Japanese visual novel learners.

![Anki add-on](https://img.shields.io/badge/Anki-add--on-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![Tests](https://img.shields.io/badge/tests-unittest-brightgreen)
![Frequency source](https://img.shields.io/badge/frequency-Yomitan%20%2B%20Jiten-7A3)

`anki_vn_sorter` reorders eligible **new** Kiku cards so the next cards you see are more likely to be common, useful, and readable with the kanji you already know. Review cards, learning cards, suspended cards, and unrelated note types are left alone.

By default it uses Bee's updateable Yomitan frequency dictionary, refreshes it weekly, and falls back safely through local caches, bundled snapshots, Jiten, and Kiku's own `FreqSort` field.

**Quick links:** [Install](#install) · [Quick start](#quick-start) · [How sorting works](#how-sorting-works) · [Frequency data and attribution](#frequency-data-and-attribution) · [Configuration](#configuration) · [Development](#development) · [Troubleshooting](#troubleshooting)

## What it does

Anki can introduce new cards by insertion order, random order, or deck order. That is not ideal for a sentence-mining backlog where thousands of new cards may mix common kana-only words, readable known-kanji words, and rare unknown-kanji words.

Anki VN Sorter adds a practical ranking layer:

| Approach | Result |
| --- | --- |
| Default Anki order | New cards appear by deck/insertion/random behavior, with no frequency or readability signal. |
| Plain frequency sorting | Common cards rise, but kana-only cards and unknown-kanji cards can dominate the queue. |
| Anki VN Sorter | Frequency stays the main signal, while a soft readability layer keeps the queue useful instead of painful. |

## Features

- **VN-first ranking:** `frequency_first_soft_v1` blends frequency with known-kanji readability.
- **Auto-updating Yomitan source:** Bee's Character Dictionary frequency dictionary is the default and refreshes weekly.
- **Jiten fallback:** switch to Jiten lists manually, or let Jiten cover Yomitan/cache failures.
- **Offline-safe load order:** fresh cache → live refresh → stale cache → bundled snapshots → Kiku `FreqSort`.
- **AnkiDroid-friendly automation:** the default `after_sync` mode runs on desktop after sync finishes.
- **Safe scope:** only matching new cards are repositioned; reviews and learning cards are untouched.
- **Manual controls:** sort, refresh, and change frequency source from Anki's Tools menu.
- **Local API:** `GET /health` and `POST /sort` for scripts, health checks, and optional timers.

## Requirements

- Anki desktop with the Kiku note type.
- Candidate cards matching the default scope: `note:Kiku is:new -is:suspended`.
- An `Expression` field on the note type, plus `FreqSort` if you want the final fallback source.
- Python 3.10+ for development scripts and tests.
- Internet access is optional at runtime: it enables refreshes, but bundled/cached data keeps sorting usable offline.

## Install

Build the add-on package:

```bash
python3 scripts/package_addon.py
```

Install `dist/anki_vn_sorter.ankiaddon` from Anki's add-ons screen, then restart Anki.

For development, symlink the source folder into Anki's `addons21` directory and restart Anki:

```bash
# Linux
mkdir -p ~/.local/share/Anki2/addons21
ln -sfn "$PWD/addon/anki_vn_sorter" ~/.local/share/Anki2/addons21/anki_vn_sorter

# macOS
mkdir -p "$HOME/Library/Application Support/Anki2/addons21"
ln -sfn "$PWD/addon/anki_vn_sorter" "$HOME/Library/Application Support/Anki2/addons21/anki_vn_sorter"
```

On Windows, place or link `addon/anki_vn_sorter` under `%APPDATA%\Anki2\addons21\anki_vn_sorter`.

## Quick start

1. Install the add-on and restart Anki.
2. Open the Anki profile that contains your Kiku deck.
3. Confirm your target cards match `note:Kiku is:new -is:suspended`.
4. Run `Tools -> Anki VN Sorter -> Sort Kiku VN Cards Now`.
5. Optional: run `Tools -> Anki VN Sorter -> Refresh Current Frequency Source Now` to force a frequency refresh.

The default automatic mode is:

```json
{
  "autoSortMode": "after_sync"
}
```

That mode is intentional. It lets Anki Desktop reorder after sync completes, which is safer if AnkiDroid also introduces or reviews cards.

## How sorting works

The default strategy is `frequency_first_soft_v1`.

The sorter tries to prioritize cards that are:

1. common in the active frequency source,
2. readable with kanji you have already matured in Kiku,
3. not blocked forever just because they are kana-only or contain one unfamiliar kanji.

Pipeline:

1. Find eligible new cards with `scopeQuery`.
2. Keep only configured note types from `modelNames`.
3. Build a known-kanji set from mature Kiku cards.
4. Load the active frequency source.
5. Score each candidate with frequency plus readability.
6. Reposition only the matching new cards through Anki's internal API.

### Known kanji

The add-on infers known kanji from mature Kiku cards.

Default mature search:

```text
note:Kiku prop:ivl>=21 -is:suspended
```

If a kanji appears in the `Expression` field of a mature Kiku note, it counts as known for prioritization. This is only a readability proxy; it is not a separate SRS, kanji grade, or pass/fail filter.

### Scoring

Frequency comes first. The sorter reads the best available rank from:

1. the configured Yomitan frequency dictionary,
2. the selected Jiten list,
3. Kiku `FreqSort`.

Then it applies soft readability adjustments:

| Card shape | Default treatment |
| --- | --- |
| All kanji known | full value, multiplier `1.00` |
| Kana-only | mild penalty, multiplier `0.92` |
| Unknown kanji | penalty of `0.18` per unknown kanji, capped at `0.54` |
| Partially-known unknown-kanji word | small bonus of `0.04 * coverage_score` |

Final ordering uses:

1. higher blended score,
2. better raw frequency rank,
3. shorter expression length when `preferShorterExpressions = true`,
4. current due position,
5. card template order,
6. card id.

Older strategies, `easy_first_tiered_v1` and `balanced_ease_v1`, remain available for compatibility, but `frequency_first_soft_v1` is the recommended default.

## Frequency data and attribution

### Default Yomitan source

Bee's updateable Character Dictionary Yomitan frequency dictionary is the default:

```json
{
  "yomitanFrequencyIndexUrl": "https://characterdictionary.tokyo/api/yomitan-frequency-index?vndb_user=u306797&display_mode=occurrence&combine_mode=average",
  "yomitanCacheTtlHours": 168
}
```

`168` hours means the add-on tries to refresh the dictionary once a week.

### Load order

When a Yomitan URL is configured, the add-on tries:

1. fresh Yomitan cache,
2. live Yomitan update URL,
3. stale Yomitan cache,
4. bundled Bee Yomitan snapshot at `addon/anki_vn_sorter/data/bee_frequency.zip`,
5. selected Jiten list,
6. bundled Jiten Global snapshot at `addon/anki_vn_sorter/data/jiten_frequency_global.csv`,
7. Kiku `FreqSort`.

Choosing a Jiten list from the Tools menu clears the Yomitan URL and makes Jiten the primary source.

### Does Jiten need attribution?

Yes. Jiten's frequency lists are published as **CC BY-SA 4.0** data, and this repository bundles Jiten-derived frequency data. Keep attribution with any redistributed package or modified frequency data.

This repo includes a packaged notice at `addon/anki_vn_sorter/data/ATTRIBUTION.md`. The bundled Bee Yomitan ZIP also contains `attribution.txt` and metadata pointing back to Jiten.

Attribution summary:

- Jiten: <https://jiten.moe/>
- Jiten source repository: <https://github.com/Sirush/Jiten>
- Jiten frequency lists license: <https://creativecommons.org/licenses/by-sa/4.0/>
- Jiten notes that it uses JMdict, JMnedict, and KANJIDIC data from the Electronic Dictionary Research and Development Group under the EDRDG license.

The Jiten application code is Apache-2.0, but the frequency-list data is CC BY-SA 4.0. Treat code and data licensing separately.

## Menus and commands

Anki menu actions:

- `Tools -> Anki VN Sorter -> Sort Kiku VN Cards Now`
- `Tools -> Anki VN Sorter -> Choose Jiten Frequency List...`
- `Tools -> Anki VN Sorter -> Set Yomitan Frequency Dictionary URL...`
- `Tools -> Anki VN Sorter -> Clear Yomitan Frequency Dictionary URL`
- `Tools -> Anki VN Sorter -> Refresh Current Frequency Source Now`

Local health check:

```bash
curl http://127.0.0.1:8767/health
```

Run a sort through the local endpoint:

```bash
curl -X POST http://127.0.0.1:8767/sort
```

Helper script:

```bash
python3 scripts/request_sort.py --force
```

`--force` ignores the helper script's local guard. The add-on still decides whether the current Anki profile has already been sorted today.

## Automatic sorting

Supported values for `autoSortMode`:

| Value | When it runs | Best for |
| --- | --- | --- |
| `after_sync` | after Anki Desktop finishes sync | most multi-device workflows; default |
| `profile_open` | when a profile opens | single-device desktop workflows |
| `manual_only` | never automatically | manual/scripting-only use |

`after_sync` is the safest default when AnkiDroid is part of the workflow because desktop reorders after sync, not before it.

## Optional systemd timer

The repo ships optional `systemd --user` units in `systemd/`. Prefer `autoSortMode = "after_sync"` if you sync cards across devices.

Install the timer:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/anki-vn-sorter.service ~/.config/systemd/user/
cp systemd/anki-vn-sorter.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now anki-vn-sorter.timer
```

The timer calls `POST http://127.0.0.1:8767/sort`. It only works while Anki is running and the target profile is open.

## Configuration

Edit `addon/anki_vn_sorter/config.json` before packaging, or open `Tools -> Add-ons -> Anki VN Sorter -> Config` inside Anki. The add-on ships `addon/anki_vn_sorter/config.md`, so Anki's config editor shows inline help.

Recommended defaults:

```json
{
  "scopeQuery": "note:Kiku is:new -is:suspended",
  "matureQuery": "",
  "matureDays": 21,
  "strategy": "frequency_first_soft_v1",
  "autoSortMode": "after_sync",
  "yomitanFrequencyIndexUrl": "https://characterdictionary.tokyo/api/yomitan-frequency-index?vndb_user=u306797&display_mode=occurrence&combine_mode=average",
  "yomitanCacheTtlHours": 168,
  "kanaOnlyMultiplier": 0.92,
  "unknownKanjiPenaltyStep": 0.18,
  "unknownKanjiPenaltyCap": 0.54,
  "partialKnownCoverageBonus": 0.04
}
```

Important keys by purpose:

| Purpose | Keys |
| --- | --- |
| Scope | `modelNames`, `scopeQuery`, `expressionField`, `freqSortField` |
| Known-kanji detection | `matureQuery`, `matureDays` |
| Ranking | `strategy`, `preferShorterExpressions`, `kanaOnlyMultiplier`, `unknownKanjiPenaltyStep`, `unknownKanjiPenaltyCap`, `partialKnownCoverageBonus`, `tierOrder`, `freqSortWeight` |
| Automation | `autoSortMode`, `httpPort` |
| Frequency sources | `yomitanFrequencyIndexUrl`, `yomitanCacheTtlHours`, `jitenFrequencyListId`, `jitenVnCsvUrl`, `jitenCacheTtlHours`, `jitenRequestTimeoutSeconds` |

## Endpoints

The add-on starts a localhost server when a profile opens.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | readiness, profile, config, last sort state, deck warnings |
| `POST /sort` | run sort and return candidate/repositioning summary |

The sort preview includes `priorityTier`, `priorityLabel`, `unknownKanjiCount`, `rankSource`, and `rank`.

## Deck behavior

The add-on repositions new cards. It does not touch review or learning cards, and it does not override Anki's scheduler.

For the sorted order to show up reliably, deck options should avoid random new-card handling. `/health` reports warnings when deck options look incompatible with manual repositioning.

## Development

Run tests:

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

The packager excludes runtime state, local add-on metadata, and bytecode files from the `.ankiaddon`.

## Repo layout

- `addon/anki_vn_sorter/`: add-on source.
- `addon/anki_vn_sorter/data/bee_frequency.zip`: bundled Bee Yomitan fallback.
- `addon/anki_vn_sorter/data/jiten_frequency_global.csv`: bundled Jiten Global fallback.
- `addon/anki_vn_sorter/data/ATTRIBUTION.md`: packaged frequency-data attribution notice.
- `scripts/package_addon.py`: package builder.
- `scripts/request_sort.py`: optional local API helper.
- `systemd/`: optional user unit templates.
- `tests/`: unit tests.

## Troubleshooting

If sorting does nothing:

- confirm Anki is running and the correct profile is open,
- confirm your cards are Kiku notes,
- confirm they match `scopeQuery`,
- confirm each note has an `Expression` field value,
- check `curl http://127.0.0.1:8767/health`.

If frequency ranking is missing:

- run `Tools -> Anki VN Sorter -> Refresh Current Frequency Source Now`,
- confirm `yomitanFrequencyIndexUrl` is blank or a valid `http(s)` index/ZIP URL,
- check whether the Yomitan or Jiten cache could be refreshed,
- confirm the bundled snapshots are present under `addon/anki_vn_sorter/data/`.

If the order shown in study still looks wrong:

- inspect deck-option warnings from `/health`,
- make sure your deck is not randomizing or re-sorting new cards after repositioning,
- confirm the target cards are still new cards after sync.

If the timer never succeeds:

- make sure Anki is running,
- make sure the correct profile is open,
- check `systemctl --user status anki-vn-sorter.timer`,
- use `/health` first; the timer cannot work if the local add-on server is not ready.
