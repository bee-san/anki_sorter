Anki Sorter settings

You can edit these keys in Anki's add-on config editor.

Main settings:

- `modelNames`
  Note types that the sorter is allowed to touch. The default supports Kiku and
  Lapis-style sentence cards:
  - `Kiku`
  - `Lapis`

- `scopeQuery`
  Which new cards are eligible to be reordered. The default is:

  ```text
  (note:"Kiku" or note:"Lapis") is:new -is:suspended
  ```

  If you add another supported note type, add it here too.

- `expressionField`
  Field containing the Japanese expression. Default: `Expression`.

- `freqSortField`
  Optional fallback frequency field. Default: `FreqSort`.

- `strategy`
  `frequency_first_soft_v1` is the default. It keeps frequency as the main
  signal, then applies soft readability penalties so common and readable cards
  rise first.

- `autoSortMode`
  Controls when the add-on runs automatically.
  Valid values:
  - `after_sync`
  - `profile_open`
  - `manual_only`

  Recommended default:
  - `manual_only`

  Manual-only sorting avoids automatic desktop reorders racing mobile sync state.
  Anki Desktop cannot detect offline AnkiDroid reviews that have not synced yet,
  so desktop `after_sync` is not inherently safe for profiles also reviewed on
  AnkiDroid.

- `syncSafetyMode`
  Additional guard for sync-adjacent automation.
  Valid values:
  - `mobile_guarded`
  - `desktop_only_allow_auto`

  Recommended default:
  - `mobile_guarded`

  `mobile_guarded` blocks sync-adjacent automatic sorting unless you manually
  confirm all devices are synced. Use `desktop_only_allow_auto` only for profiles
  where desktop-only automatic sorting is an intentional opt-in and no phone or
  tablet can have unsynced reviews.

AnkiDroid sync safety:

- Safe default:

  ```json
  {
    "autoSortMode": "manual_only",
    "syncSafetyMode": "mobile_guarded"
  }
  ```

- Manual safe sequence for AnkiDroid users:
  1. Sync AnkiDroid and wait for it to finish.
  2. Sync Anki Desktop and resolve any sync prompts.
  3. Sort with `Tools -> Anki Sorter -> Sort Cards Now`.
  4. Sync Anki Desktop again before studying elsewhere.

- Desktop-only automation opt-in:

  ```json
  {
    "autoSortMode": "after_sync",
    "syncSafetyMode": "desktop_only_allow_auto"
  }
  ```

  Use this only for desktop-only profiles. Desktop automation cannot prove that
  AnkiDroid has already uploaded offline reviews.

- Native AnkiDroid auto-sync is useful hygiene, not a sorter safety guarantee.
  The AnkiDroid manual says **Automatic synchronization** syncs "every time you
  open and close the app" and is limited to "once every ten minutes"; it is not
  a time-of-day scheduler. Source: AnkiDroid manual, Preferences -> AnkiDroid ->
  Automatic synchronization: https://docs.ankidroid.org/manual.html#settings

- Tasker / Automate can trigger AnkiDroid's experimental sync intent. The
  AnkiDroid API documents `Action:com.ichi2.anki.DO_SYNC`, says attempts more
  often than "once every 5 minutes" can show a "server is busy" error, and notes
  the target must be `Activity`. Source: AnkiDroid API, Sync Intent:
  https://github.com/ankidroid/Anki-Android/wiki/AnkiDroid-API#sync-intent

Ranking settings:

- `preferShorterExpressions`
  If `true`, shorter expressions win ties after the main score and raw rank.

- `kanaOnlyMultiplier`
  Soft penalty applied to kana-only cards in `frequency_first_soft_v1`.
  Lower values make kana-only cards wait longer unless they are much more frequent.

- `unknownKanjiPenaltyStep`
  Per-unknown-kanji penalty in `frequency_first_soft_v1`.

- `unknownKanjiPenaltyCap`
  Maximum total unknown-kanji penalty in `frequency_first_soft_v1`.

- `partialKnownCoverageBonus`
  Small bonus for partially-known cards in `frequency_first_soft_v1`.
  This only applies to cards that still have at least one unknown kanji.

- `readingExposureWeight`
  Optional boost from Reading Exposure Exporter media in Anki's
  `collection.media` directory. `0.0` disables the boost. The default is `0.18`.

- `tierOrder`
  Controls the tier order used by `easy_first_tiered_v1`.
  It does not affect `frequency_first_soft_v1`.
  Valid labels:
  - `all_kanji_known`
  - `kana_only`
  - `one_unknown_kanji`
  - `two_unknown_kanji`
  - `three_plus_unknown_kanji`

- `freqSortWeight`
  Weight to give the note's `FreqSort` field when Jiten/Yomitan data is unavailable.
  Must be between `0.0` and `1.0`.

Known kanji settings:

- `matureDays`
  Used to build the default mature-card query when `matureQuery` is blank.

- `matureQuery`
  Optional override for the mature-card search.
  Leave it as `""` if you want `matureDays` and `modelNames` to control maturity.

Frequency settings:

- `jitenFrequencyListId`
  Built-in Jiten list to use.
  Valid values:
  - `global`
  - `kanji`
  - `anime`
  - `audio`
  - `drama`
  - `manga`
  - `movie`
  - `non_fiction`
  - `novel`
  - `video_game`
  - `visual_novel`
  - `web_novel`

  Recommended default:
  - `global`

  You can change this from:
  - `Tools -> Anki Sorter -> Choose Jiten Frequency List...`

- `yomitanFrequencyIndexUrl`
  Yomitan frequency dictionary index or ZIP URL.
  The default is Bee's updateable frequency dictionary from Character Dictionary.
  Leave it as `""` to use the selected Jiten list.
  When set, Yomitan is tried first and Jiten remains the fallback if refresh fails.
  You can set or clear this from:
  - `Tools -> Anki Sorter -> Set Yomitan Frequency Dictionary URL...`
  - `Tools -> Anki Sorter -> Clear Yomitan Frequency Dictionary URL`

  Choosing a Jiten list from the menu clears this Yomitan override.

- `jitenVnCsvUrl`
  Optional direct CSV URL override.
  Leave it as `""` unless you want to bypass the built-in Jiten list selector.

- `jitenDiscoveryUrl`
  Legacy setting retained for compatibility. The add-on now uses Jiten's API
  directly for the built-in list selector.

- `jitenCacheTtlHours`
  How long the cached Jiten CSV is considered fresh before the add-on tries to
  refresh it again.

- `yomitanCacheTtlHours`
  How long the cached Yomitan frequency dictionary is considered fresh before
  the add-on tries to refresh it again.
  The default is `168`, so Bee's Yomitan dictionary updates weekly.

- `jitenRequestTimeoutSeconds`
  Network timeout for Jiten and Yomitan requests.

The add-on also ships with a bundled Bee Yomitan snapshot and a bundled Jiten
Global CSV snapshot.
