# Anki VN Sorter

`anki_vn_sorter` is an Anki add-on for prioritizing new Kiku cards so the next cards you see tend to feel easier.

It is designed for a Japanese visual novel workflow:

- only new cards are reordered
- review and learning cards are untouched
- Kiku cards are prioritized by how easy they should be to read now
- VN frequency is used as a tie-breaker, not the main decision rule
- by default, automatic sorting happens after desktop sync
- a local HTTP endpoint still exists for manual or timer-based runs

## What It Does

By default, the add-on sorts eligible new cards into these tiers:

1. kana-only cards
2. cards whose kanji are all already known
3. cards with 1 unknown kanji
4. cards with 2 unknown kanji
5. cards with 3 or more unknown kanji

Within a tier, the add-on prefers:

- better Jiten Visual Novel frequency rank
- then Kiku `FreqSort` as fallback
- then shorter expressions
- then stable card order tie-breakers

This is intentionally not a general “difficulty score.” It is a practical new-card prioritizer.

## Scope

Default scope:

- note type: `Kiku`
- search: `note:Kiku is:new -is:suspended`

By default, non-Kiku notes are ignored even if they are new.

## How “Known Kanji” Works

The add-on infers known kanji from mature Kiku cards in your collection.

Default mature search:

- `note:Kiku prop:ivl>=21 -is:suspended`

If a kanji appears in the `Expression` field of a mature Kiku note, it counts as known for prioritization.

This is only a proxy for real ease, but it works well enough for daily new-card ordering.

## Requirements

- Anki desktop
- Kiku note type for the cards you want sorted
- Linux only if you want the included `systemd --user` timer

AnkiConnect is not required for sorting. The add-on runs inside Anki and exposes its own localhost endpoint.

## Install

Build the packaged add-on:

```bash
python3 scripts/package_addon.py
```

### Option 1: Install the `.ankiaddon`

Use this if you want a normal end-user install.

1. Build [dist/anki_vn_sorter.ankiaddon](/home/bee/Documents/src/github/anki_sorter/dist/anki_vn_sorter.ankiaddon).
2. Open Anki.
3. Open the add-ons screen in Anki and install the `.ankiaddon` file.
4. Restart Anki after the install finishes.
5. Open the profile you want to sort.

### Option 2: Install from the source folder

Use this if you want the Anki install to track your local working copy.

Copy install:

```bash
mkdir -p ~/.local/share/Anki2/addons21/anki_vn_sorter
cp -r addon/anki_vn_sorter/* ~/.local/share/Anki2/addons21/anki_vn_sorter/
```

Symlink install:

```bash
mkdir -p ~/.local/share/Anki2/addons21
ln -sfn /home/bee/Documents/src/github/anki_sorter/addon/anki_vn_sorter ~/.local/share/Anki2/addons21/anki_vn_sorter
```

Then restart Anki and open the profile you want to sort.

## Update an Existing Install

If you installed with the `.ankiaddon`:

1. Rebuild the package:

```bash
python3 scripts/package_addon.py
```

2. Reinstall the new [dist/anki_vn_sorter.ankiaddon](/home/bee/Documents/src/github/anki_sorter/dist/anki_vn_sorter.ankiaddon) from Anki’s add-ons screen.
3. Restart Anki.

If you installed by copying the source folder:

1. Copy the updated files again:

```bash
cp -r addon/anki_vn_sorter/* ~/.local/share/Anki2/addons21/anki_vn_sorter/
```

2. Restart Anki.

If you installed by symlink:

- the files are already updated when this repo changes
- just restart Anki

## Quick Start

1. Install the add-on using one of the methods above.

2. Open Anki and load the profile you want to sort.

3. Optional: run it once manually from Anki:

- `Tools -> Anki VN Sorter -> Sort Kiku VN Cards Now`

4. Automatic mode is enabled by default through the add-on setting:

- `autoSortMode = "after_sync"`

That means the add-on will sort automatically after a successful sync on desktop.

This default is intentional. A reorder that happens before desktop sync can interfere with new-card syncing between AnkiDroid and desktop; the issue you linked recommends reordering after syncing instead. Source: [Ankidroid new cards are not syncing with Anki desktop](https://skerritt.blog/ankidroid-new-cards-are-not-syncing-with-anki-desktop/).

5. Optional: only if you want a Linux timer for a single-device workflow, install the `systemd --user` timer described below.

## Automatic Sorting

Recommended automatic mode:

- `after_sync`

Other modes:

- `manual_only`
- `profile_open`

Set them in `Tools -> Add-ons -> Anki VN Sorter -> Config`.

Recommended default:

```json
{
  "autoSortMode": "after_sync"
}
```

Why `after_sync` is the default:

- it avoids reordering before sync
- that is the safer choice if you study new cards on AnkiDroid
- it keeps automatic behavior inside Anki instead of relying on an external timer

## Optional Systemd Timer

The repo still ships checkout-independent `systemd --user` unit templates in [systemd](/home/bee/Documents/src/github/anki_sorter/systemd).

This is optional and not the recommended path if you sync new cards across devices. A timer can run before you sync desktop, which is exactly the situation you wanted to avoid.

Install them:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/anki-vn-sorter.service ~/.config/systemd/user/
cp systemd/anki-vn-sorter.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now anki-vn-sorter.timer
```

The timer works by calling:

- `POST http://127.0.0.1:8767/sort`

Important behavior:

- it only works while Anki is running and the profile is open
- the add-on enforces once-per-day sorting per Anki profile
- the timer retries hourly until Anki is available
- it may run before you sync desktop, so prefer `autoSortMode = "after_sync"` for multi-device use

## Manual Commands

Manual HTTP check:

```bash
curl http://127.0.0.1:8767/health
```

Manual HTTP sort:

```bash
curl -X POST http://127.0.0.1:8767/sort
```

Optional helper script:

```bash
python3 scripts/request_sort.py --force
```

`--force` ignores the helper script’s local guard. The add-on still decides whether the current profile has already been sorted today.

## Configuration

Edit [addon/anki_vn_sorter/config.json](/home/bee/Documents/src/github/anki_sorter/addon/anki_vn_sorter/config.json) before packaging, or open `Tools -> Add-ons -> Anki VN Sorter -> Config` in Anki.

The add-on now ships [config.md](/home/bee/Documents/src/github/anki_sorter/addon/anki_vn_sorter/config.md), so the config editor shows a help panel with the editable settings.

Important keys:

- `modelNames`
- `scopeQuery`
- `matureQuery`
- `matureDays`
- `httpPort`
- `strategy`
- `autoSortMode`
- `tierOrder`
- `preferShorterExpressions`
- `freqSortWeight`
- `jitenDiscoveryUrl`
- `jitenVnCsvUrl`
- `jitenCacheTtlHours`
- `jitenRequestTimeoutSeconds`
- `expressionField`
- `readingField`
- `freqSortField`

Current strategies:

- `easy_first_tiered_v1`: default, tiered by unknown kanji count
- `balanced_ease_v1`: older weighted heuristic

Tier labels for `tierOrder`:

- `kana_only`
- `all_kanji_known`
- `one_unknown_kanji`
- `two_unknown_kanji`
- `three_plus_unknown_kanji`

Recommended default:

```json
{
  "strategy": "easy_first_tiered_v1",
  "autoSortMode": "after_sync"
}
```

If Jiten discovery fails on your machine, set `jitenVnCsvUrl` explicitly.
Leave `matureQuery` as `""` if you want `matureDays` to control what counts as mature.

## Endpoints

The add-on starts a localhost server when a profile opens.

Endpoints:

- `GET /health`
- `POST /sort`

`/health` returns readiness, profile, config, last successful sort date, and deck warnings.

`/sort` returns a summary including:

- whether anything was applied
- candidate count
- repositioned count
- warnings
- a preview of the top-ranked cards

The preview includes:

- `priorityTier`
- `priorityLabel`
- `unknownKanjiCount`
- `rankSource`
- `rank`

## Deck Behavior

The add-on repositions new cards. It does not override Anki’s own scheduling model for review cards.

For the sorted order to show up reliably, your deck options should avoid random new-card handling. The add-on will warn when deck options look incompatible with manual repositioning.

## Repo Layout

- [addon/anki_vn_sorter](/home/bee/Documents/src/github/anki_sorter/addon/anki_vn_sorter): add-on source
- [scripts/request_sort.py](/home/bee/Documents/src/github/anki_sorter/scripts/request_sort.py): optional manual helper
- [scripts/package_addon.py](/home/bee/Documents/src/github/anki_sorter/scripts/package_addon.py): package builder
- [systemd](/home/bee/Documents/src/github/anki_sorter/systemd): user unit templates
- [tests](/home/bee/Documents/src/github/anki_sorter/tests): test suite

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

The packager excludes runtime state and bytecode files from the `.ankiaddon`.

## Troubleshooting

If the timer never succeeds:

- make sure Anki is running
- make sure the correct profile is open
- check `curl http://127.0.0.1:8767/health`
- check `systemctl --user status anki-vn-sorter.timer`

If sorting does nothing:

- confirm your new cards are actually Kiku notes
- confirm they match `scopeQuery`
- confirm the note has an `Expression` field value

If frequency ranking is missing:

- set `jitenVnCsvUrl` directly
- check whether the Jiten cache could be refreshed

If the order shown in study still looks wrong:

- inspect deck-option warnings from `/health`
- make sure your deck is not randomizing or re-sorting new cards after repositioning
