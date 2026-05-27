Anki VN Sorter settings

You can edit these keys in Anki's add-on config editor.

Main settings:

- `scopeQuery`
  Which new cards are eligible to be reordered.

- `modelNames`
  Note types that the sorter should treat as supported.

- `strategy`
  `frequency_first_soft_v1` is the default.
  It blends frequency with soft readability penalties, so very common kana-only
  and one-unknown-kanji cards can still rise early.
  `easy_first_tiered_v1` keeps the stricter bucketed behavior.
  `balanced_ease_v1` keeps the older weighted heuristic.

- `autoSortMode`
  Controls when the add-on runs automatically.
  Valid values:
  - `after_sync`
  - `profile_open`
  - `manual_only`

  Recommended default:
  - `after_sync`

  This is the safest mode if you also study on AnkiDroid, because the reorder happens after desktop sync, not before it.

- `tierOrder`
  Controls the tier order used by `easy_first_tiered_v1`.
  It does not affect `frequency_first_soft_v1`.
  Valid labels:
  - `all_kanji_known`
  - `kana_only`
  - `one_unknown_kanji`
  - `two_unknown_kanji`
  - `three_plus_unknown_kanji`

- `preferShorterExpressions`
  If `true`, shorter expressions win ties after the main score and raw rank.

- `freqSortWeight`
  Weight to give Kiku `FreqSort` when the selected Jiten frequency list is unavailable.
  Must be between `0.0` and `1.0`.

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

Known kanji settings:

- `matureDays`
  Used to build the default mature-card query when `matureQuery` is blank.

- `matureQuery`
  Optional override for the mature-card search.
  Leave it as `""` if you want `matureDays` to control maturity.

Network settings:

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
  - `Tools -> Anki VN Sorter -> Choose Jiten Frequency List...`

- `jitenVnCsvUrl`
  Optional direct CSV URL override.
  Leave it as `""` unless you want to bypass the built-in Jiten list selector.

- `yomitanFrequencyIndexUrl`
  Yomitan frequency dictionary index or ZIP URL.
  The default is Bee's updateable frequency dictionary from Character Dictionary.
  Leave it as `""` to use the selected Jiten list.
  When set, Yomitan is tried first and Jiten remains the fallback if refresh fails.
  You can set or clear this from:
  - `Tools -> Anki VN Sorter -> Set Yomitan Frequency Dictionary URL...`
  - `Tools -> Anki VN Sorter -> Clear Yomitan Frequency Dictionary URL`

  Choosing a Jiten list from the menu clears this Yomitan override.

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
Yomitan load order is:

- fresh user cache
- live Yomitan download
- stale user cache
- bundled Bee snapshot
- selected Jiten source

Jiten load order is:

- fresh user cache
- live Jiten download
- stale user cache
- bundled snapshot

Field settings:

- `expressionField`
- `readingField`
- `freqSortField`

The add-on reads `expressionField` and `freqSortField` today.
`readingField` is reserved for future ranking improvements.
