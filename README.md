# Anki VN Sorter

Frequency-aware new-card ordering for Kiku decks, built for Japanese visual novel learners.

![Anki add-on](https://img.shields.io/badge/Anki-add--on-blue)
![Python](https://img.shields.io/badge/Python-3.x-3776AB)
![Tests](https://img.shields.io/badge/tests-unittest-brightgreen)
![Frequency source](https://img.shields.io/badge/frequency-Yomitan%20%2B%20Jiten-7A3)

`anki_vn_sorter` reorders only your eligible new cards so the next Kiku cards
you see are more likely to be useful, common, and readable with the kanji you
already know.

It ships with Bee's Yomitan frequency dictionary, refreshes it once a week by
default, and falls back safely to local caches, the bundled snapshot, Jiten, and
Kiku `FreqSort`.

**Quick Links:** [Install](#install) | [Quick Start](#quick-start) | [Algorithm](#the-algorithm) | [Yomitan Frequency Updates](#yomitan-frequency-updates) | [Configuration](#configuration) | [Troubleshooting](#troubleshooting)

## Why Use It?

Anki can introduce new cards in insertion order, random order, or simple deck
order. That is not enough for a sentence-mining workflow where 2,000 new cards
can include a mix of easy known-kanji words, common kana-only words, and rare
unknown-kanji words.

Anki VN Sorter gives you a practical middle ground:

| Approach | What happens |
| --- | --- |
| Default Anki new-card order | Cards appear by insertion/random/deck behavior, without knowing what is common or readable. |
| Plain frequency sorting | Common words rise, but kana-only and unknown-kanji cards can overwhelm the queue. |
| Anki VN Sorter | Frequency is the main signal, then a readability layer keeps the queue useful instead of painful. |

## What You Get

- **Special VN-first ranking algorithm:** `frequency_first_soft_v1` blends frequency with known-kanji readability.
- **Auto-updating Yomitan frequency:** Bee's Yomitan dictionary is the default source and refreshes weekly.
- **Offline-safe fallback:** stale cache, bundled Bee snapshot, Jiten, bundled Jiten Global, then Kiku `FreqSort`.
- **AnkiDroid-safe automation:** automatic sorting defaults to `after_sync`, so desktop reorders after sync instead of before it.
- **New cards only:** review and learning cards are untouched.
- **Kiku-focused defaults:** `note:Kiku is:new -is:suspended` is the default scope.
- **Manual controls:** run, refresh, or switch frequency sources from Anki's Tools menu.
- **Local HTTP endpoint:** useful for scripts, health checks, and optional timer workflows.

## Install

Build the packaged add-on:

```bash
python3 scripts/package_addon.py
```

Then install `dist/anki_vn_sorter.ankiaddon` from Anki's add-ons screen and
restart Anki.

For development, install the source folder directly:

```bash
mkdir -p ~/.local/share/Anki2/addons21
ln -sfn "$PWD/addon/anki_vn_sorter" ~/.local/share/Anki2/addons21/anki_vn_sorter
```

Restart Anki after installing or updating.

## Quick Start

1. Install the add-on.
2. Restart Anki and open the profile you want to sort.
3. Make sure your target cards are Kiku notes matching `note:Kiku is:new -is:suspended`.
4. Run `Tools -> Anki VN Sorter -> Sort Kiku VN Cards Now`, or let it run automatically after sync.
5. Check `Tools -> Anki VN Sorter -> Refresh Current Frequency Source Now` if you want to force a Yomitan/Jiten refresh.

Default automatic mode:

```json
{
  "autoSortMode": "after_sync"
}
```

That mode is intentional: it keeps the reorder inside Anki and runs after
desktop sync, which is safer when AnkiDroid is also part of the workflow.

## The Algorithm

The default strategy is `frequency_first_soft_v1`.

In plain English, the sorter tries to show cards that are:

1. common in Bee's Yomitan frequency dictionary or the selected Jiten list
2. readable with kanji you already know
3. still flexible enough to let very common kana-only or partially-known words appear early

The pipeline:

1. Find eligible new cards with `scopeQuery`.
2. Keep only supported note types from `modelNames`.
3. Build a known-kanji set from mature Kiku cards.
4. Load the active frequency source.
5. Score every candidate with frequency plus readability.
6. Reposition only the matching new cards through Anki's internal API.

### Known Kanji

The add-on infers known kanji from mature Kiku cards.

Default mature search:

```text
note:Kiku prop:ivl>=21 -is:suspended
```

If a kanji appears in the `Expression` field of a mature Kiku note, it counts
as known for prioritization. This is a proxy for readability, not a separate
SRS or grading system.

### Scoring

The score starts with an absolute frequency score from the best available
source:

1. configured Yomitan dictionary
2. selected Jiten list
3. Kiku `FreqSort`

Then the sorter applies readability adjustments:

| Card shape | Default treatment |
| --- | --- |
| All kanji known | full value, multiplier `1.00` |
| Kana-only | mild penalty, multiplier `0.92` |
| Unknown kanji | penalty of `0.18` per unknown kanji, capped at `0.54` |
| Partially-known unknown-kanji word | small bonus of `0.04 * coverage_score` |

Final ordering uses:

1. higher blended score
2. better raw frequency rank
3. shorter expression length when `preferShorterExpressions = true`
4. current due
5. card template order
6. card id

The older `easy_first_tiered_v1` and `balanced_ease_v1` strategies are still
available, but `frequency_first_soft_v1` is the recommended default.

## Yomitan Frequency Updates

Bee's updateable Yomitan frequency dictionary is the default:

```json
{
  "yomitanFrequencyIndexUrl": "https://characterdictionary.tokyo/api/yomitan-frequency-index?vndb_user=u306797&display_mode=occurrence&combine_mode=average",
  "yomitanCacheTtlHours": 168
}
```

`168` hours means the add-on tries to refresh the dictionary once a week.

Load order:

1. fresh Yomitan cache
2. live Yomitan update URL
3. stale Yomitan cache
4. bundled Bee snapshot at `data/bee_frequency.zip`
5. selected Jiten list
6. bundled Jiten Global snapshot
7. Kiku `FreqSort`

Menu actions:

- `Tools -> Anki VN Sorter -> Set Yomitan Frequency Dictionary URL...`
- `Tools -> Anki VN Sorter -> Clear Yomitan Frequency Dictionary URL`
- `Tools -> Anki VN Sorter -> Refresh Current Frequency Source Now`

Choosing a Jiten list clears the Yomitan URL and uses Jiten instead.

## Automatic Sorting

Recommended mode:

```json
{
  "autoSortMode": "after_sync"
}
```

Supported values:

- `after_sync`
- `profile_open`
- `manual_only`

`after_sync` maps to Anki's sync-finished hook. This is the safest default for
multi-device use because the desktop reorder happens after sync, not before it.

## Manual Commands

Health check:

```bash
curl http://127.0.0.1:8767/health
```

Run a sort:

```bash
curl -X POST http://127.0.0.1:8767/sort
```

Helper script:

```bash
python3 scripts/request_sort.py --force
```

`--force` ignores the helper script's local guard. The add-on still decides
whether the current profile has already been sorted today.

## Optional Systemd Timer

The repo ships `systemd --user` unit templates in `systemd/`.

This path is optional. Prefer `autoSortMode = "after_sync"` if you sync new
cards across devices.

Install the timer:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/anki-vn-sorter.service ~/.config/systemd/user/
cp systemd/anki-vn-sorter.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now anki-vn-sorter.timer
```

The timer calls `POST http://127.0.0.1:8767/sort`. It only works while Anki is
running and the profile is open.

## Configuration

Edit `addon/anki_vn_sorter/config.json` before packaging, or open
`Tools -> Add-ons -> Anki VN Sorter -> Config` in Anki.

The add-on ships `addon/anki_vn_sorter/config.md`, so Anki's config editor
shows a help panel.

Important keys:

- `modelNames`
- `scopeQuery`
- `matureQuery`
- `matureDays`
- `strategy`
- `autoSortMode`
- `yomitanFrequencyIndexUrl`
- `yomitanCacheTtlHours`
- `jitenFrequencyListId`
- `jitenCacheTtlHours`
- `expressionField`
- `freqSortField`
- `tierOrder`
- `kanaOnlyMultiplier`
- `unknownKanjiPenaltyStep`
- `unknownKanjiPenaltyCap`
- `partialKnownCoverageBonus`

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

## Endpoints

The add-on starts a localhost server when a profile opens.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | readiness, profile, config, last sort state, deck warnings |
| `POST /sort` | run sort and return candidate/repositioning summary |

The sort preview includes `priorityTier`, `priorityLabel`,
`unknownKanjiCount`, `rankSource`, and `rank`.

## Deck Behavior

The add-on repositions new cards. It does not touch review or learning cards,
and it does not override Anki's scheduler.

For the sorted order to show up reliably, your deck options should avoid random
new-card handling. `/health` reports warnings when deck options look
incompatible with manual repositioning.

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

The packager excludes runtime state, local add-on metadata, and bytecode files
from the `.ankiaddon`.

## Repo Layout

- `addon/anki_vn_sorter/`: add-on source
- `addon/anki_vn_sorter/data/bee_frequency.zip`: bundled Bee Yomitan fallback
- `scripts/package_addon.py`: package builder
- `scripts/request_sort.py`: optional manual helper
- `systemd/`: optional user unit templates
- `tests/`: test suite

## Troubleshooting

If sorting does nothing:

- confirm your new cards are Kiku notes
- confirm they match `scopeQuery`
- confirm the note has an `Expression` field value
- check `curl http://127.0.0.1:8767/health`

If frequency ranking is missing:

- run `Tools -> Anki VN Sorter -> Refresh Current Frequency Source Now`
- confirm `yomitanFrequencyIndexUrl` is blank or a valid `http(s)` index/ZIP URL
- check whether the Yomitan or Jiten cache could be refreshed

If the order shown in study still looks wrong:

- inspect deck-option warnings from `/health`
- make sure your deck is not randomizing or re-sorting new cards after repositioning

If the timer never succeeds:

- make sure Anki is running
- make sure the correct profile is open
- check `systemctl --user status anki-vn-sorter.timer`
