Anki VN Sorter settings

You can edit these keys in Anki's add-on config editor.

Main settings:

- `scopeQuery`
  Which new cards are eligible to be reordered.

- `modelNames`
  Note types that the sorter should treat as supported.

- `strategy`
  `easy_first_tiered_v1` is the default.
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
  Valid labels:
  - `kana_only`
  - `all_kanji_known`
  - `one_unknown_kanji`
  - `two_unknown_kanji`
  - `three_plus_unknown_kanji`

- `preferShorterExpressions`
  If `true`, shorter expressions win ties inside the same tier and rank.

- `freqSortWeight`
  Weight to give Kiku `FreqSort` when Jiten Visual Novel frequency is unavailable.
  Must be between `0.0` and `1.0`.

Known kanji settings:

- `matureDays`
  Used to build the default mature-card query when `matureQuery` is blank.

- `matureQuery`
  Optional override for the mature-card search.
  Leave it as `""` if you want `matureDays` to control maturity.

Network settings:

- `jitenVnCsvUrl`
  Optional direct CSV URL.

- `jitenDiscoveryUrl`
  Page used to discover the Visual Novel CSV when `jitenVnCsvUrl` is blank.

- `jitenCacheTtlHours`
  How long the cached Jiten CSV is considered fresh.

- `jitenRequestTimeoutSeconds`
  Network timeout for Jiten requests.

Field settings:

- `expressionField`
- `readingField`
- `freqSortField`

The add-on reads `expressionField` and `freqSortField` today.
`readingField` is reserved for future ranking improvements.
