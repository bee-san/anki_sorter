# Anki VN Sorter

`anki_vn_sorter` is an Anki add-on for prioritizing new Kiku cards so the next cards you see tend to feel easier.

It is designed for a Japanese visual novel workflow:

- only new cards are reordered
- review and learning cards are untouched
- Kiku cards are prioritized by how easy they should be to read now
- Jiten frequency is the main decision signal, with soft readability penalties
- by default, automatic sorting happens after desktop sync
- the add-on defaults to Jiten `Global` and can switch to other Jiten lists
- the add-on auto-refreshes the selected Jiten list from Jiten's export API
- a bundled Jiten `Global` snapshot is included for offline fallback
- a local HTTP endpoint still exists for manual or timer-based runs

## What It Does

By default, the add-on uses a blended score:

- better Jiten frequency rank from the selected list is the main signal
- `all_kanji_known` cards get no penalty
- `kana_only` cards get a mild penalty, so they still rise when they are much more common
- cards with unknown kanji get a stronger penalty, but super common ones can still appear early
- partially-known unknown-kanji cards get a small bonus

This is intentionally not a general “difficulty score.” It is a practical
Pareto-style new-card prioritizer.

## Algorithm Summary

The default strategy is `frequency_first_soft_v1`.

In plain terms, the add-on tries to show:

1. words that are very common in the selected Jiten list
2. words that should be readable with what you already know
3. some high-value kana-only and unknown-kanji words early, but not enough to make the queue painful

The score works like this:

- start with an absolute frequency score from the selected Jiten list
- keep `all_kanji_known` words at full value
- apply a small penalty to `kana_only` words, so they mix in without taking over
- apply a larger penalty as unknown kanji increases
- give a small bonus to partially-known unknown-kanji words

So the queue is not hard-bucketed. Very common easy words rise first, but
extremely common kana-only or partially-known words can still break in early.

## Algorithm

The default strategy is `frequency_first_soft_v1`.

At a high level, the add-on does this:

1. Find eligible cards with `scopeQuery`.
2. Keep only `is:new` cards from supported note types.
3. Build a known-kanji set from mature Kiku cards.
4. Load the selected Jiten frequency list.
5. Compute a blended score for each new card.
6. Sort by that score and stable tie-breakers.
7. Reposition only the matching new cards in Anki.

More concretely:

1. Candidate selection:
   The default query is `note:Kiku is:new -is:suspended`.
   Review and learning cards are ignored.

2. Known-kanji extraction:
   The add-on searches mature cards using `matureQuery` or the generated
   `matureDays` query.
   It reads the `Expression` field from those mature Kiku notes and extracts
   kanji characters.
   If a kanji appears there, it counts as known.

3. Frequency source selection:
   The active list comes from `jitenFrequencyListId`.
   The default is `global`.
   The add-on tries to use:
   - the fresh cache for the selected list
   - the live Jiten export API for the selected list
   - the stale cache for the selected list
   - the bundled `Global` snapshot when the selected list is `global`
   - Kiku `FreqSort` only if no Jiten data is available

4. Per-card features:
   For each candidate card, the add-on reads:
   - `Expression`
   - extracted kanji count
   - known kanji count
   - Jiten rank from the selected list
   - Kiku `FreqSort` rank as fallback

5. Blended scoring:
   The default score is:
   - absolute frequency score from Jiten, or `FreqSort` as fallback
   - multiplied by a readability adjustment:
     - `all_kanji_known`: `1.00`
     - `kana_only`: `0.92`
     - unknown kanji: `1 - min(0.18 * unknown_kanji_count, 0.54)`
   - plus a small partial-known bonus:
     - `0.04 * coverage_score` for cards that still have unknown kanji

   This means:
   - similar-frequency known-kanji cards usually beat kana-only cards
   - super common kana-only cards can still rise early
   - super common one-unknown-kanji cards can outrank weaker easy cards
   - harder unknown-kanji cards still sink unless their frequency is very strong

6. Final ordering:
   Cards are sorted by:
   - higher blended score
   - then better raw rank
   - then shorter expression length when `preferShorterExpressions = true`
   - then current due
   - then card template order
   - then card id

   The older `easy_first_tiered_v1` mode still exists if you want strict buckets.

7. Repositioning:
   The add-on calls Anki’s internal new-card reposition API.
   It starts from the minimum due among the eligible cards and only reorders the
   matching new cards.
   Non-matching cards are left alone as much as possible.

There are also optional strategies, `easy_first_tiered_v1` and
`balanced_ease_v1`, but the default and recommended path is
`frequency_first_soft_v1`.

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
- `Tools -> Anki VN Sorter -> Choose Jiten Frequency List...`
- `Tools -> Anki VN Sorter -> Refresh Current Jiten Frequency List Now`

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
- `kanaOnlyMultiplier`
- `unknownKanjiPenaltyStep`
- `unknownKanjiPenaltyCap`
- `partialKnownCoverageBonus`
- `jitenFrequencyListId`
- `jitenDiscoveryUrl`
- `jitenVnCsvUrl`
- `jitenCacheTtlHours`
- `jitenRequestTimeoutSeconds`
- `expressionField`
- `readingField`
- `freqSortField`

Current strategies:

- `frequency_first_soft_v1`: default, frequency-first with soft readability penalties
- `easy_first_tiered_v1`: optional strict bucket mode
- `balanced_ease_v1`: older weighted heuristic

Tier labels for `tierOrder`:

- `all_kanji_known`
- `kana_only`
- `one_unknown_kanji`
- `two_unknown_kanji`
- `three_plus_unknown_kanji`

Recommended default:

```json
{
  "strategy": "frequency_first_soft_v1",
  "kanaOnlyMultiplier": 0.92,
  "unknownKanjiPenaltyStep": 0.18,
  "unknownKanjiPenaltyCap": 0.54,
  "partialKnownCoverageBonus": 0.04,
  "autoSortMode": "after_sync"
}
```

Leave `matureQuery` as `""` if you want `matureDays` to control what counts as mature.

Jiten behavior:

- by default, `jitenFrequencyListId` is `global`
- switch lists from `Tools -> Anki VN Sorter -> Choose Jiten Frequency List...`
- `Global` and `Kanji` are listed first; media-specific lists are marked as such
- `jitenVnCsvUrl` is only an optional manual override now
- the add-on refreshes the selected list cache when it becomes stale
- if the live download fails, it falls back to the cache for that list
- if the selected list has no usable cache and is `global`, it falls back to the bundled snapshot

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

- run `Tools -> Anki VN Sorter -> Refresh Current Jiten Frequency List Now`
- if you use a custom mirror, set `jitenVnCsvUrl` directly
- check whether the Jiten cache could be refreshed

If the order shown in study still looks wrong:

- inspect deck-option warnings from `/health`
- make sure your deck is not randomizing or re-sorting new cards after repositioning
